from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventRecoveryError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventArchiveRecoveryService,
    LLMAgentTaskEventArchiveService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventRetentionService,
    LLMAgentTaskEventService,
)


def _services():
    active_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=active_store)
    query_service = LLMAgentTaskEventQueryService(store=active_store)
    retention_service = LLMAgentTaskEventRetentionService(query_service=query_service)
    archive_service = LLMAgentTaskEventArchiveService(retention_service=retention_service)
    recovery_service = LLMAgentTaskEventArchiveRecoveryService(
        archive_service=archive_service, active_query_service=query_service
    )
    return emitter, query_service, archive_service, recovery_service


def _old(days=60):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _save_at(store, event, when):
    store.delete(event.task_id, event.event_id)
    store.save(replace(event, occurred_at=when))


def _archive_one_old_event(emitter, query_service, archive_service, task_id="task-1"):
    old_event = emitter.emit(task_id, CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit(task_id, CONTEXT_UPDATED)  # latest -- stays active
    archive_service.archive(task_id)
    return old_event


# --- restore missing events -----------------------------------------------------------------


def test_plan_restore_identifies_missing_events():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = _archive_one_old_event(emitter, query_service, archive_service)

    plan = recovery_service.plan_restore("task-1")

    assert old_event.event_id in plan.missing
    assert old_event.event_id in plan.available_in_archive
    assert plan.conflicts == ()


def test_recover_restores_missing_events():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = _archive_one_old_event(emitter, query_service, archive_service)

    plan = recovery_service.plan_restore("task-1")
    result = recovery_service.recover(plan)

    assert old_event.event_id in result.restored
    active_ids = {event.event_id for event in query_service.query(task_id="task-1")}
    assert old_event.event_id in active_ids
    # a successful restore moves the event -- the archived copy is gone
    assert archive_service.list_archived("task-1") == []


def test_plan_restore_rejects_blank_task_id():
    _, _, _, recovery_service = _services()

    with pytest.raises(InvalidAgentTaskEventRecoveryError):
        recovery_service.plan_restore("")


def test_recover_rejects_non_plan_argument():
    _, _, _, recovery_service = _services()

    with pytest.raises(InvalidAgentTaskEventRecoveryError):
        recovery_service.recover("not-a-plan")


# --- already-restored events ------------------------------------------------------------------


def test_already_restored_event_is_reported_and_not_touched_again():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = _archive_one_old_event(emitter, query_service, archive_service)
    recovery_service.recover(recovery_service.plan_restore("task-1"))

    # the archive copy is gone now (moved), so re-checking this specific id
    # requires asking for it explicitly by event_id
    second_plan = recovery_service.plan_restore("task-1", event_ids=[old_event.event_id])

    assert old_event.event_id in second_plan.already_active
    assert old_event.event_id not in second_plan.missing

    second_result = recovery_service.recover(second_plan)
    assert old_event.event_id not in second_result.restored
    assert old_event.event_id in second_result.already_restored


# --- conflicting event identity --------------------------------------------------------------


def test_conflicting_identity_is_reported_not_overwritten():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = _archive_one_old_event(emitter, query_service, archive_service)

    # simulate a conflicting active event reappearing under the same event_id
    # but with different content (a different event_type)
    conflicting = replace(old_event, event_type=LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    query_service.store.save(conflicting)

    plan = recovery_service.plan_restore("task-1")

    assert any(c.event_id == old_event.event_id for c in plan.conflicts)
    assert old_event.event_id not in plan.missing
    assert old_event.event_id not in plan.already_active

    result = recovery_service.recover(plan)

    assert any(c.event_id == old_event.event_id for c in result.unresolved_conflicts)
    assert old_event.event_id not in result.restored
    # the active event must remain exactly as it was found -- never overwritten
    remaining_active = [e for e in query_service.query(task_id="task-1") if e.event_id == old_event.event_id][0]
    assert remaining_active.event_type == LIFECYCLE_TRANSITIONED
    assert remaining_active.payload == {"to_state": "planned"}
    # and the archived copy is left in place too, never silently discarded
    assert any(e.event_id == old_event.event_id for e in archive_service.list_archived("task-1"))


# --- mixed missing + existing events ------------------------------------------------------------


def test_mixed_missing_and_already_active_events_handled_independently():
    emitter, query_service, archive_service, recovery_service = _services()
    first = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, first, _old(days=90))
    second = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, second, _old(days=80))
    emitter.emit("task-1", CONTEXT_UPDATED)  # keeps something active/latest
    archive_service.archive("task-1")

    # restore only `first` ahead of time, leaving `second` still archived
    recovery_service.recover(recovery_service.plan_restore("task-1", event_ids=[first.event_id]))

    # first is no longer archived at all (moved out already) -- explicitly
    # naming it is how a caller re-checks its restoration status
    plan = recovery_service.plan_restore("task-1", event_ids=[first.event_id, second.event_id])
    assert first.event_id in plan.already_active
    assert second.event_id in plan.missing

    result = recovery_service.recover(plan)
    assert second.event_id in result.restored
    assert first.event_id in result.already_restored


# --- preserved ordering and metadata --------------------------------------------------------------


def test_recovery_preserves_identity_timestamp_and_payload():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    old_timestamp = _old()
    _save_at(query_service.store, old_event, old_timestamp)
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    recovery_service.recover(recovery_service.plan_restore("task-1"))

    restored = [e for e in query_service.query(task_id="task-1") if e.event_id == old_event.event_id][0]
    assert restored.event_id == old_event.event_id
    assert restored.occurred_at == old_timestamp
    assert restored.payload == {"to_state": "planned"}


def test_plan_resulting_order_previews_post_recovery_chronology():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    old_timestamp = _old(days=90)
    _save_at(query_service.store, old_event, old_timestamp)
    latest = emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    plan = recovery_service.plan_restore("task-1")

    assert plan.resulting_order == (old_event.event_id, latest.event_id)


# --- correlation/parent relationships --------------------------------------------------------------


def test_recovery_preserves_correlation_and_parent_metadata():
    emitter, query_service, archive_service, recovery_service = _services()
    parent = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-a")
    _save_at(query_service.store, parent, _old())
    child = emitter.emit(
        "task-1", CONTEXT_UPDATED, parent_event_id=parent.event_id, correlation_id="corr-a"
    )
    _save_at(query_service.store, child, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")  # only child is eligible; parent stays active (protected)

    recovery_service.recover(recovery_service.plan_restore("task-1"))

    restored_child = [e for e in query_service.query(task_id="task-1") if e.event_id == child.event_id][0]
    assert restored_child.parent_event_id == parent.event_id
    assert restored_child.correlation_id == "corr-a"


# --- repeated recovery is idempotent ------------------------------------------------------------------


def test_repeated_recovery_is_idempotent():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = _archive_one_old_event(emitter, query_service, archive_service)

    plan = recovery_service.plan_restore("task-1", event_ids=[old_event.event_id])
    first = recovery_service.recover(plan)
    second = recovery_service.recover(plan)

    assert old_event.event_id in first.restored
    assert old_event.event_id not in second.restored
    assert old_event.event_id in second.already_restored
    assert len(query_service.query(task_id="task-1")) == 2  # not duplicated


def test_repeated_recovery_with_unscoped_plan_is_also_idempotent():
    emitter, query_service, archive_service, recovery_service = _services()
    old_event = _archive_one_old_event(emitter, query_service, archive_service)

    plan = recovery_service.plan_restore("task-1")  # no explicit event_ids
    first = recovery_service.recover(plan)
    second = recovery_service.recover(plan)  # re-derives against an now-empty archive scope

    assert old_event.event_id in first.restored
    assert second.restored == ()
    assert len(query_service.query(task_id="task-1")) == 2  # not duplicated


# --- post-recovery verification -----------------------------------------------------------------------


def test_recovery_result_embeds_verification():
    emitter, query_service, archive_service, recovery_service = _services()
    _archive_one_old_event(emitter, query_service, archive_service)

    result = recovery_service.recover(recovery_service.plan_restore("task-1"))

    assert result.verification.task_id == "task-1"
    assert result.verification.is_valid is True


# --- failed recovery leaves existing events unchanged -----------------------------------------------------


def test_conflicting_recovery_leaves_other_valid_restores_unaffected():
    emitter, query_service, archive_service, recovery_service = _services()
    conflicting_old = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, conflicting_old, _old(days=90))
    clean_old = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, clean_old, _old(days=80))
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    # introduce a conflict for conflicting_old only
    query_service.store.save(replace(conflicting_old, event_type=LIFECYCLE_TRANSITIONED))

    plan = recovery_service.plan_restore("task-1")
    result = recovery_service.recover(plan)

    assert clean_old.event_id in result.restored  # unaffected by the other conflict
    assert any(c.event_id == conflicting_old.event_id for c in result.unresolved_conflicts)

    unchanged_active = [e for e in query_service.query(task_id="task-1") if e.event_id == conflicting_old.event_id][0]
    assert unchanged_active.event_type == LIFECYCLE_TRANSITIONED  # untouched


def test_empty_archive_recovery_is_a_clean_no_op():
    _, _, _, recovery_service = _services()

    plan = recovery_service.plan_restore("task-1")
    result = recovery_service.recover(plan)

    assert plan.missing == ()
    assert result.restored == ()
    assert result.verification.is_valid is True
