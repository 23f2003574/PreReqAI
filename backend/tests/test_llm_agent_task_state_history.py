import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import (
    CREATED,
    FAILED,
    PLANNED,
    READY,
    RUNNING,
    InvalidTaskTransitionError,
    UnknownAgentTaskError,
)
from backend.agent_task_state_history import (
    InvalidTaskTransitionRecordError,
    JsonAgentTaskTransitionStore,
    LLMAgentTaskLifecycleHistoryTrackedService,
    LLMAgentTaskStateHistoryService,
    TaskTransitionRecord,
)


def _history_service():
    return LLMAgentTaskStateHistoryService()


def _tracked_service():
    return LLMAgentTaskLifecycleHistoryTrackedService()


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


# --- record_transition ---------------------------------------------------------------


def test_record_transition_appends_entry():
    service = _history_service()

    record = service.record_transition("task-1", None, CREATED)

    assert isinstance(record, TaskTransitionRecord)
    assert record.task_id == "task-1"
    assert record.from_state is None
    assert record.to_state == CREATED
    assert record.reason is None


def test_record_transition_rejects_unknown_to_state():
    service = _history_service()

    with pytest.raises(InvalidTaskTransitionRecordError):
        service.record_transition("task-1", CREATED, "not-a-real-state")


def test_record_transition_rejects_unknown_from_state():
    service = _history_service()

    with pytest.raises(InvalidTaskTransitionRecordError):
        service.record_transition("task-1", "not-a-real-state", PLANNED)


def test_record_transition_rejects_missing_task_id():
    service = _history_service()

    with pytest.raises(InvalidTaskTransitionRecordError):
        service.record_transition("", None, CREATED)


def test_record_transition_rejects_non_string_reason():
    service = _history_service()

    with pytest.raises(InvalidTaskTransitionRecordError):
        service.record_transition("task-1", None, CREATED, reason=123)


# --- successful transitions recorded via the tracked lifecycle service ----------------


def test_tracked_service_records_successful_transitions():
    service = _tracked_service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED, reason="kick off planning")
    service.transition(task.task_id, READY, reason="dependencies resolved")

    history = service._history_service.get_history(task.task_id)

    assert [record.to_state for record in history] == [CREATED, PLANNED, READY]
    assert history[0].from_state is None
    assert history[1].from_state == CREATED
    assert history[1].reason == "kick off planning"
    assert history[2].reason == "dependencies resolved"


def test_tracked_service_delegates_lifecycle_behavior_unchanged():
    service = _tracked_service()
    task = service.create(_definition())

    assert task.current_state == CREATED

    with pytest.raises(UnknownAgentTaskError):
        service.get("does-not-exist")


# --- invalid transitions are not recorded ---------------------------------------------


def test_invalid_transition_is_not_recorded():
    service = _tracked_service()
    task = service.create(_definition())

    with pytest.raises(InvalidTaskTransitionError):
        service.transition(task.task_id, RUNNING)

    history = service._history_service.get_history(task.task_id)
    assert [record.to_state for record in history] == [CREATED]  # only creation was recorded


def test_repeated_same_state_transition_is_not_recorded_again():
    service = _tracked_service()
    task = service.create(_definition())
    service.transition(task.task_id, PLANNED, reason="first reason")

    service.transition(task.task_id, PLANNED, reason="ignored, no-op")

    history = service._history_service.get_history(task.task_id)
    assert [record.to_state for record in history] == [CREATED, PLANNED]


# --- chronological ordering -------------------------------------------------------------


def test_get_history_is_chronologically_ordered():
    service = _history_service()
    service.record_transition("task-1", None, CREATED)
    service.record_transition("task-1", CREATED, PLANNED)
    service.record_transition("task-1", PLANNED, READY)
    service.record_transition("task-1", READY, FAILED)

    history = service.get_history("task-1")

    assert [record.to_state for record in history] == [CREATED, PLANNED, READY, FAILED]
    for earlier, later in zip(history, history[1:]):
        assert earlier.occurred_at <= later.occurred_at


def test_get_history_missing_task_returns_empty_list():
    service = _history_service()

    assert service.get_history("does-not-exist") == []


def test_get_history_rejects_missing_task_id():
    service = _history_service()

    with pytest.raises(InvalidTaskTransitionRecordError):
        service.get_history("")


# --- filtering ---------------------------------------------------------------------------


def test_get_history_filters_by_to_state():
    service = _history_service()
    service.record_transition("task-1", None, CREATED)
    service.record_transition("task-1", CREATED, PLANNED)
    service.record_transition("task-1", PLANNED, READY)

    filtered = service.get_history("task-1", to_state=PLANNED)

    assert [record.to_state for record in filtered] == [PLANNED]


def test_get_history_filters_by_time_range():
    service = _history_service()
    now = datetime.now(timezone.utc)
    service.record_transition("task-1", None, CREATED)
    service.record_transition("task-1", CREATED, PLANNED)

    only_after = service.get_history("task-1", since=now + timedelta(hours=1))
    everything = service.get_history("task-1", since=now - timedelta(hours=1), until=now + timedelta(hours=1))

    assert only_after == []
    assert [record.to_state for record in everything] == [CREATED, PLANNED]


def test_get_history_rejects_non_datetime_time_bounds():
    service = _history_service()

    with pytest.raises(InvalidTaskTransitionRecordError):
        service.get_history("task-1", since="not-a-datetime")


# --- get_latest ----------------------------------------------------------------------------


def test_get_latest_returns_most_recent_record():
    service = _history_service()
    service.record_transition("task-1", None, CREATED)
    service.record_transition("task-1", CREATED, PLANNED)
    latest = service.record_transition("task-1", PLANNED, READY)

    assert service.get_latest("task-1") == latest


def test_get_latest_returns_none_for_task_with_no_history():
    service = _history_service()

    assert service.get_latest("does-not-exist") is None


# --- multiple tasks remain isolated -------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    service = _history_service()
    service.record_transition("task-1", None, CREATED)
    service.record_transition("task-1", CREATED, PLANNED)
    service.record_transition("task-2", None, CREATED)

    assert [record.to_state for record in service.get_history("task-1")] == [CREATED, PLANNED]
    assert [record.to_state for record in service.get_history("task-2")] == [CREATED]


# --- immutability -------------------------------------------------------------------------


def test_transition_record_is_frozen():
    record = TaskTransitionRecord(task_id="task-1", from_state=None, to_state=CREATED)

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.to_state = PLANNED


def test_history_cannot_mutate_previously_recorded_entries():
    service = _history_service()
    service.record_transition("task-1", None, CREATED)

    first_read = service.get_history("task-1")
    first_read.clear()  # mutating the returned list...
    first_read.append("garbage")

    second_read = service.get_history("task-1")
    assert [record.to_state for record in second_read] == [CREATED]  # ...never reaches the stored trail


# --- JSON persistence ------------------------------------------------------------------------


def test_json_store_round_trips_history_across_service_instances(tmp_path):
    path = tmp_path / "transitions.json"

    service_a = LLMAgentTaskStateHistoryService(store=JsonAgentTaskTransitionStore(path))
    service_a.record_transition("task-1", None, CREATED)
    service_a.record_transition("task-1", CREATED, PLANNED, reason="kick off planning")

    service_b = LLMAgentTaskStateHistoryService(store=JsonAgentTaskTransitionStore(path))
    history = service_b.get_history("task-1")

    assert [record.to_state for record in history] == [CREATED, PLANNED]
    assert history[1].reason == "kick off planning"
