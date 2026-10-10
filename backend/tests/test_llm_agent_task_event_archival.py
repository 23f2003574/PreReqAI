from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventArchiveError,
    LIFECYCLE_TRANSITIONED,
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
    return emitter, query_service, archive_service


def _old(days=60):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _save_at(store, event, when):
    store.delete(event.task_id, event.event_id)
    store.save(replace(event, occurred_at=when))


# --- archive eligible events -----------------------------------------------------------------


def test_archive_moves_eligible_events():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)  # recent, and the latest event -- stays active

    result = archive_service.archive("task-1")

    assert any(c.event_id == old_event.event_id for c in result.archived)
    active_ids = {event.event_id for event in query_service.query(task_id="task-1")}
    assert old_event.event_id not in active_ids


def test_archive_rejects_blank_task_id():
    _, _, archive_service = _services()

    with pytest.raises(InvalidAgentTaskEventArchiveError):
        archive_service.archive("")


# --- preserve complete event identity/metadata ------------------------------------------------


def test_archived_event_preserves_full_identity_and_metadata():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit(
        "task-1",
        LIFECYCLE_TRANSITIONED,
        payload={"to_state": "planned"},
        correlation_id="corr-1",
        operation_id="op-1",
    )
    old_timestamp = _old()
    _save_at(query_service.store, old_event, old_timestamp)
    emitter.emit("task-1", CONTEXT_UPDATED)

    archive_service.archive("task-1")

    archived = archive_service.list_archived("task-1")
    assert len(archived) == 1
    restored_event = archived[0]
    assert restored_event.event_id == old_event.event_id
    assert restored_event.task_id == old_event.task_id
    assert restored_event.event_type == old_event.event_type
    assert restored_event.occurred_at == old_timestamp
    assert restored_event.correlation_id == "corr-1"
    assert restored_event.operation_id == "op-1"
    assert restored_event.payload == {"to_state": "planned"}


# --- archived events excluded from active-event reads --------------------------------------------


def test_archived_events_are_excluded_from_active_query():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    latest = emitter.emit("task-1", CONTEXT_UPDATED)

    archive_service.archive("task-1")

    active_ids = {event.event_id for event in query_service.query(task_id="task-1")}
    assert old_event.event_id not in active_ids
    assert latest.event_id in active_ids


def test_archived_events_are_invisible_to_projection_until_restored():
    from backend.agent_task_events import LLMAgentTaskEventProjectionService

    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)

    projection_service = LLMAgentTaskEventProjectionService(query_service=query_service)
    before_projection = projection_service.project("task-1")
    assert before_projection.event_count == 2

    archive_service.archive("task-1")

    after_projection = projection_service.project("task-1")
    assert after_projection.event_count == 1  # archived event no longer counted


# --- archived-event listing ----------------------------------------------------------------------


def test_list_archived_supports_time_window_and_limit():
    emitter, query_service, archive_service = _services()
    first = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, first, _old(days=90))
    second = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, second, _old(days=80))
    emitter.emit("task-1", CONTEXT_UPDATED)  # stays active as the latest

    archive_service.archive("task-1")

    all_archived = archive_service.list_archived("task-1")
    assert [event.event_id for event in all_archived] == [first.event_id, second.event_id]

    limited = archive_service.list_archived("task-1", limit=1)
    assert [event.event_id for event in limited] == [second.event_id]

    windowed = archive_service.list_archived("task-1", start_time=_old(days=85))
    assert [event.event_id for event in windowed] == [second.event_id]


def test_list_archived_empty_for_task_with_nothing_archived():
    _, _, archive_service = _services()

    assert archive_service.list_archived("task-1") == []


# --- no-op when nothing is eligible ---------------------------------------------------------------


def test_archive_is_a_no_op_when_nothing_eligible():
    emitter, _, archive_service = _services()
    emitter.emit("task-1", CONTEXT_UPDATED)  # recent -- not eligible

    result = archive_service.archive("task-1")

    assert result.archived == ()
    assert result.already_archived == ()
    assert result.skipped == ()


def test_archive_empty_task_stream_cleanly():
    _, _, archive_service = _services()

    result = archive_service.archive("task-1")

    assert result.archived == ()


# --- repeated archive is idempotent ------------------------------------------------------------------


def test_repeated_archive_is_idempotent():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)

    first = archive_service.archive("task-1")
    second = archive_service.archive("task-1")

    assert any(c.event_id == old_event.event_id for c in first.archived)
    assert second.archived == ()
    assert len(archive_service.list_archived("task-1")) == 1


# --- restore without duplicate events ------------------------------------------------------------------


def test_restore_moves_event_back_to_active_store():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    result = archive_service.restore("task-1")

    assert any(c.event_id == old_event.event_id for c in result.restored)
    active_ids = {event.event_id for event in query_service.query(task_id="task-1")}
    assert old_event.event_id in active_ids
    assert archive_service.list_archived("task-1") == []


def test_restore_preserves_original_identity_and_timestamp():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    old_timestamp = _old()
    _save_at(query_service.store, old_event, old_timestamp)
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    archive_service.restore("task-1", event_ids=[old_event.event_id])

    restored = [event for event in query_service.query(task_id="task-1") if event.event_id == old_event.event_id][0]
    assert restored.event_id == old_event.event_id
    assert restored.occurred_at == old_timestamp
    assert restored.payload == {"to_state": "planned"}


def test_repeated_restore_of_the_same_event_is_idempotent():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    archive_service.restore("task-1", event_ids=[old_event.event_id])
    active_count_before = len(query_service.query(task_id="task-1"))

    # the event is now active and no longer in the archive at all -- a second
    # restore() request for the same id finds nothing left to move
    second_result = archive_service.restore("task-1", event_ids=[old_event.event_id])

    assert second_result.restored == ()
    assert old_event.event_id in second_result.not_found
    assert len(query_service.query(task_id="task-1")) == active_count_before


def test_restore_does_not_duplicate_an_event_already_present_in_active_store():
    emitter, query_service, archive_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    archive_service.archive("task-1")

    # defensive scenario: the archived copy still exists, but an event sharing
    # its identity has also (independently) reappeared in the active store
    query_service.store.save(old_event)

    result = archive_service.restore("task-1", event_ids=[old_event.event_id])

    assert result.restored == ()
    assert any(c.event_id == old_event.event_id for c in result.already_restored)
    matching_active = [e for e in query_service.query(task_id="task-1") if e.event_id == old_event.event_id]
    assert len(matching_active) == 1  # not duplicated


def test_restore_reports_not_found_for_unknown_event_id():
    _, _, archive_service = _services()

    result = archive_service.restore("task-1", event_ids=["does-not-exist"])

    assert result.not_found == ("does-not-exist",)
    assert result.restored == ()


def test_restore_rejects_non_list_event_ids():
    _, _, archive_service = _services()

    with pytest.raises(InvalidAgentTaskEventArchiveError):
        archive_service.restore("task-1", event_ids="not-a-list")


# --- correlation metadata survives archival --------------------------------------------------------


def test_correlation_and_parent_metadata_survive_archive_and_restore():
    # root is referenced by child's own parent_event_id, so Commit #9's own
    # protection keeps root active/unarchivable -- only child (which nothing
    # references) is actually eligible, and its own correlation/parent
    # metadata must survive the round trip intact.
    emitter, query_service, archive_service = _services()
    root = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-1")
    _save_at(query_service.store, root, _old())
    child = emitter.emit(
        "task-1", CONTEXT_UPDATED, correlation_id="corr-1", parent_event_id=root.event_id
    )
    _save_at(query_service.store, child, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)  # keeps something active/latest

    archive_service.archive("task-1")

    archived = {event.event_id: event for event in archive_service.list_archived("task-1")}
    assert child.event_id in archived
    assert root.event_id not in archived  # protected: still referenced as a parent
    assert archived[child.event_id].parent_event_id == root.event_id
    assert archived[child.event_id].correlation_id == "corr-1"

    archive_service.restore("task-1")
    restored = {event.event_id: event for event in query_service.query(task_id="task-1")}
    assert restored[child.event_id].parent_event_id == root.event_id
    assert restored[child.event_id].correlation_id == "corr-1"


# --- reuses Commit #9's protections (parent is never archived while referenced) ----------------------


def test_referenced_parent_is_never_archived():
    emitter, query_service, archive_service = _services()
    parent = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    _save_at(query_service.store, parent, _old())
    child = emitter.emit("task-2", CONTEXT_UPDATED, parent_event_id=parent.event_id)
    _save_at(query_service.store, child, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)
    emitter.emit("task-2", CONTEXT_UPDATED)

    archive_service.archive("task-1")
    archive_service.archive("task-2")

    assert archive_service.list_archived("task-1") == []  # parent still protected, never archived
    active_ids = {event.event_id for event in query_service.query(task_id="task-1")}
    assert parent.event_id in active_ids


# --- does not modify authoritative task state -------------------------------------------------------


def test_archive_and_restore_do_not_touch_lifecycle_state():
    from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService

    lifecycle_service = LLMAgentTaskLifecycleService()
    task = lifecycle_service.create({"agent_id": "a", "scope_id": "s", "objective": "o"})

    emitter, query_service, archive_service = _services()
    old_event = emitter.emit(task.task_id, CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit(task.task_id, CONTEXT_UPDATED)

    archive_service.archive(task.task_id)
    archive_service.restore(task.task_id)

    unchanged = lifecycle_service.get(task.task_id)
    assert unchanged.current_state == task.current_state
    assert unchanged.updated_at == task.updated_at
