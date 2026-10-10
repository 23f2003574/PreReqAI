from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    InMemoryAgentTaskEventProjectionStore,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventProjectionError,
    JsonAgentTaskEventProjectionStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventProjectionService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import CREATED, FAILED, PLANNED, READY, RUNNING

import pytest


def _services():
    event_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    projection_service = LLMAgentTaskEventProjectionService(query_service=query_service)
    return emitter, projection_service


# --- projection from a normal event stream ------------------------------------------------


def test_project_reconstructs_state_from_normal_stream():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    projection = projection_service.project("task-1")

    assert projection.task_id == "task-1"
    assert projection.current_state == READY
    assert projection.event_count == 2
    assert projection.last_error_reference is None


def test_project_rejects_blank_task_id():
    _, projection_service = _services()

    with pytest.raises(InvalidAgentTaskEventProjectionError):
        projection_service.project("")


# --- latest state/event calculation ---------------------------------------------------------


def test_last_event_id_and_timestamp_reflect_most_recent_event():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    last = emitter.emit("task-1", DEPENDENCY_ADDED)

    projection = projection_service.project("task-1")

    assert projection.last_event_id == last.event_id
    assert projection.last_event_at == last.occurred_at


def test_active_retry_reference_tracks_latest_retry_schedule_state():
    emitter, projection_service = _services()
    scheduled = emitter.emit("task-1", "retry_scheduled")

    projection = projection_service.project("task-1")
    assert projection.active_retry_reference == scheduled.event_id

    emitter.emit("task-1", "retry_cancelled")
    cancelled_projection = projection_service.project("task-1")
    assert cancelled_projection.active_retry_reference is None


def test_active_context_reference_tracks_latest_context_update():
    emitter, projection_service = _services()
    emitter.emit("task-1", CONTEXT_UPDATED)
    latest_context = emitter.emit("task-1", CONTEXT_UPDATED)

    projection = projection_service.project("task-1")

    assert projection.active_context_reference == latest_context.event_id


# --- empty task stream -----------------------------------------------------------------------


def test_empty_stream_projects_cleanly():
    _, projection_service = _services()

    projection = projection_service.project("task-1")

    assert projection.current_state == CREATED
    assert projection.event_count == 0
    assert projection.last_event_id is None
    assert projection.last_event_at is None
    assert projection.last_error_reference is None
    assert projection.active_retry_reference is None
    assert projection.active_context_reference is None


# --- refresh replacing stale derived data -----------------------------------------------------


def test_refresh_persists_and_replaces_stale_projection():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    first = projection_service.refresh("task-1")

    assert projection_service.get("task-1") == first
    assert first.current_state == PLANNED

    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    second = projection_service.refresh("task-1")

    assert projection_service.get("task-1") == second
    assert second.current_state == READY
    assert second != first


def test_project_alone_never_persists_anything():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    projection_service.project("task-1")

    assert projection_service.get("task-1") is None


def test_get_returns_none_when_never_refreshed():
    _, projection_service = _services()

    assert projection_service.get("task-1") is None


# --- repeated projection is deterministic ------------------------------------------------------


def test_repeated_projection_is_deterministic():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    first = projection_service.project("task-1")
    second = projection_service.project("task-1")

    assert first.task_id == second.task_id
    assert first.current_state == second.current_state
    assert first.last_event_id == second.last_event_id
    assert first.last_event_at == second.last_event_at
    assert first.event_count == second.event_count
    assert first.last_error_reference == second.last_error_reference
    assert first.active_retry_reference == second.active_retry_reference
    assert first.active_context_reference == second.active_context_reference


# --- malformed/invalid event sequence handling --------------------------------------------------


def test_invalid_transition_surfaces_as_last_error_reference():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    bad_event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})  # illegal jump

    projection = projection_service.project("task-1")

    assert projection.last_error_reference == bad_event.event_id
    assert projection.current_state == CREATED  # rejected transition never applied


def test_terminal_state_still_projects_cleanly_with_trailing_errors():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    trailing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    projection = projection_service.project("task-1")

    assert projection.current_state == FAILED
    assert projection.last_error_reference == trailing.event_id


def test_lifecycle_event_missing_to_state_does_not_error():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)  # legitimate legacy event, no payload

    projection = projection_service.project("task-1")

    assert projection.current_state == CREATED
    assert projection.last_error_reference is None
    assert projection.event_count == 1


# --- projection does not mutate authoritative task state ------------------------------------------


def test_projection_does_not_mutate_stored_events():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    before = emitter.get("task-1")
    projection_service.project("task-1")
    projection_service.refresh("task-1")
    after = emitter.get("task-1")

    assert before == after
    assert len(after) == 1


def test_projection_service_has_no_mutating_task_methods():
    _, projection_service = _services()

    assert not hasattr(projection_service, "emit")
    assert not hasattr(projection_service, "transition")


# --- get() returns persisted derived state when supported ------------------------------------------


def test_get_reads_persisted_projection_without_replaying():
    emitter, projection_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    refreshed = projection_service.refresh("task-1")

    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})  # not yet refreshed

    stale_read = projection_service.get("task-1")

    assert stale_read == refreshed
    assert stale_read.current_state == PLANNED  # still the last-refreshed value, not re-replayed


def test_get_persists_across_json_store_instances(tmp_path):
    path = tmp_path / "projections.json"
    event_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    service_a = LLMAgentTaskEventProjectionService(
        query_service=query_service, store=JsonAgentTaskEventProjectionStore(path)
    )
    service_a.refresh("task-1")

    service_b = LLMAgentTaskEventProjectionService(
        query_service=query_service, store=JsonAgentTaskEventProjectionStore(path)
    )
    projection = service_b.get("task-1")

    assert projection is not None
    assert projection.current_state == PLANNED


def test_get_rejects_blank_task_id():
    _, projection_service = _services()

    with pytest.raises(InvalidAgentTaskEventProjectionError):
        projection_service.get("")


def test_projection_store_defaults_to_in_memory():
    projection_service = LLMAgentTaskEventProjectionService()

    assert isinstance(projection_service.store, InMemoryAgentTaskEventProjectionStore)
