from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventArchiveVerificationError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventArchiveService,
    LLMAgentTaskEventArchiveVerificationService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventRetentionService,
    LLMAgentTaskEventService,
)
from backend.agent_task_events.models import AgentTaskEvent


def _services():
    active_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=active_store)
    query_service = LLMAgentTaskEventQueryService(store=active_store)
    retention_service = LLMAgentTaskEventRetentionService(query_service=query_service)
    archive_service = LLMAgentTaskEventArchiveService(retention_service=retention_service)
    verification_service = LLMAgentTaskEventArchiveVerificationService(
        archive_service=archive_service, active_query_service=query_service
    )
    return emitter, query_service, archive_service, verification_service


def _old(days=60):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _save_at(store, event, when):
    store.delete(event.task_id, event.event_id)
    store.save(replace(event, occurred_at=when))


# --- valid archive -----------------------------------------------------------------------------


def test_valid_archive_verifies_clean():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    result = verification_service.verify("task-1")

    assert result.is_valid is True
    assert result.checked_count == 1
    assert result.missing_events == ()
    assert result.mismatches == ()
    assert result.duplicate_events == ()


def test_verify_rejects_blank_task_id():
    _, _, _, verification_service = _services()

    with pytest.raises(InvalidAgentTaskEventArchiveVerificationError):
        verification_service.verify("")


def test_verify_rejects_non_list_event_ids():
    _, _, _, verification_service = _services()

    with pytest.raises(InvalidAgentTaskEventArchiveVerificationError):
        verification_service.verify("task-1", event_ids="not-a-list")


# --- missing archived event ----------------------------------------------------------------------


def test_missing_event_id_is_reported():
    _, _, _, verification_service = _services()

    result = verification_service.verify("task-1", event_ids=["does-not-exist"])

    assert result.is_valid is False
    assert result.missing_events == ("does-not-exist",)


def test_event_still_active_and_not_archived_is_not_missing():
    emitter, query_service, archive_service, verification_service = _services()
    active_event = emitter.emit("task-1", CONTEXT_UPDATED)  # recent, never archived

    result = verification_service.verify("task-1", event_ids=[active_event.event_id])

    assert active_event.event_id not in result.missing_events
    assert result.is_valid is True


# --- metadata mismatch ------------------------------------------------------------------------------


def test_task_id_field_mismatch_is_reported():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    # corrupt the archive directly: an event filed under task-1's own bucket
    # whose internal task_id field disagrees with that key
    mismatched = AgentTaskEvent(
        task_id="task-99", event_type=CONTEXT_UPDATED, event_id=old_event.event_id, occurred_at=_old()
    )
    archive_service.archive_store.delete("task-1", old_event.event_id)
    archive_service.archive_store._events.setdefault("task-1", []).append(mismatched)

    result = verification_service.verify("task-1")

    assert result.is_valid is False
    assert any(m.field == "task_id" and m.event_id == old_event.event_id for m in result.mismatches)


def test_malformed_event_type_is_reported():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    archive_service.archive_store.delete("task-1", old_event.event_id)
    malformed = AgentTaskEvent(task_id="task-1", event_type="", event_id=old_event.event_id, occurred_at=_old())
    archive_service.archive_store.save(malformed)

    result = verification_service.verify("task-1")

    assert result.is_valid is False
    assert any(m.event_id == old_event.event_id and m.field == "event_type" for m in result.mismatches)


# --- duplicate active/archived event -----------------------------------------------------------------


def test_duplicate_event_in_both_stores_is_reported():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    # simulate a corrupted state: the archived event also reappears active
    query_service.store.save(archive_service.list_archived("task-1")[0])

    result = verification_service.verify("task-1")

    assert result.is_valid is False
    assert old_event.event_id in result.duplicate_events


def test_no_duplicate_reported_for_normal_archive():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    result = verification_service.verify("task-1")

    assert result.duplicate_events == ()


# --- broken correlation reference ------------------------------------------------------------------


def test_dangling_parent_reference_is_reported():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED, parent_event_id="ghost-parent")
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    result = verification_service.verify("task-1")

    assert result.is_valid is False
    assert any(
        m.event_id == old_event.event_id and m.field == "parent_event_id" for m in result.mismatches
    )


def test_correlation_mismatch_with_active_parent_is_reported():
    emitter, query_service, archive_service, verification_service = _services()
    # parent stays active (protected, since child references it) with one correlation_id
    parent = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-a")
    _save_at(query_service.store, parent, _old())
    child = emitter.emit(
        "task-1", CONTEXT_UPDATED, parent_event_id=parent.event_id, correlation_id="corr-b"
    )
    _save_at(query_service.store, child, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")  # only child is eligible; parent stays active (protected)

    result = verification_service.verify("task-1")

    assert result.is_valid is False
    assert any(
        m.event_id == child.event_id and m.field == "correlation_id" for m in result.mismatches
    )


def test_valid_parent_reference_across_stores_is_not_flagged():
    emitter, query_service, archive_service, verification_service = _services()
    parent = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-a")
    _save_at(query_service.store, parent, _old())
    child = emitter.emit(
        "task-1", CONTEXT_UPDATED, parent_event_id=parent.event_id, correlation_id="corr-a"
    )
    _save_at(query_service.store, child, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    result = verification_service.verify("task-1")

    assert result.is_valid is True


# --- replayable archived stream ---------------------------------------------------------------------


def test_replayable_archived_stream_verifies_valid():
    emitter, query_service, archive_service, verification_service = _services()
    first = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    _save_at(query_service.store, first, _old(days=90))
    second = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "ready"})
    _save_at(query_service.store, second, _old(days=80))
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    result = verification_service.verify("task-1")

    assert result.is_valid is True


# --- empty archive -----------------------------------------------------------------------------------


def test_empty_archive_verifies_cleanly():
    _, _, _, verification_service = _services()

    result = verification_service.verify("task-1")

    assert result.is_valid is True
    assert result.checked_count == 0
    assert result.missing_events == ()
    assert result.mismatches == ()
    assert result.duplicate_events == ()


# --- deterministic repeated verification --------------------------------------------------------------


def test_repeated_verification_is_deterministic():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    first = verification_service.verify("task-1")
    second = verification_service.verify("task-1")

    assert first == second


def test_verification_does_not_mutate_stores():
    emitter, query_service, archive_service, verification_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    before_active = query_service.query(task_id="task-1")
    before_archived = archive_service.list_archived("task-1")
    verification_service.verify("task-1")
    verification_service.verify("task-1")
    after_active = query_service.query(task_id="task-1")
    after_archived = archive_service.list_archived("task-1")

    assert before_active == after_active
    assert before_archived == after_archived


def test_verification_service_has_no_mutating_methods():
    _, _, _, verification_service = _services()

    assert not hasattr(verification_service, "restore")
    assert not hasattr(verification_service, "archive")
    assert not hasattr(verification_service, "delete")
