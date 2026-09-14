import dataclasses

import pytest

from backend.agent_task_events import (
    AgentTaskEvent,
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    InvalidAgentTaskEventError,
    JsonAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventService,
    READINESS_CHANGED,
)


def _service():
    return LLMAgentTaskEventService()


# --- emit --------------------------------------------------------------------------------


def test_emit_appends_event():
    service = _service()

    event = service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})

    assert isinstance(event, AgentTaskEvent)
    assert event.task_id == "task-1"
    assert event.event_type == LIFECYCLE_TRANSITIONED
    assert event.payload == {"to_state": "planned"}
    assert event.event_id
    assert event.occurred_at is not None


def test_emit_defaults_payload_to_none():
    service = _service()

    event = service.emit("task-1", DEPENDENCY_ADDED)

    assert event.payload is None


def test_emit_rejects_missing_task_id():
    service = _service()

    with pytest.raises(InvalidAgentTaskEventError):
        service.emit("", LIFECYCLE_TRANSITIONED)


def test_emit_rejects_missing_event_type():
    service = _service()

    with pytest.raises(InvalidAgentTaskEventError):
        service.emit("task-1", "")


def test_emit_rejects_non_dict_payload():
    service = _service()

    with pytest.raises(InvalidAgentTaskEventError):
        service.emit("task-1", LIFECYCLE_TRANSITIONED, payload="not-a-dict")


def test_emit_accepts_any_event_type_not_only_known_ones():
    service = _service()

    event = service.emit("task-1", "some_future_event_kind")

    assert event.event_type == "some_future_event_kind"


# --- get / retrieval -----------------------------------------------------------------------


def test_get_returns_emitted_events():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    service.emit("task-1", DEPENDENCY_ADDED)

    events = service.get("task-1")

    assert [event.event_type for event in events] == [LIFECYCLE_TRANSITIONED, DEPENDENCY_ADDED]


def test_get_missing_task_returns_empty_list():
    service = _service()

    assert service.get("does-not-exist") == []


def test_get_rejects_missing_task_id():
    service = _service()

    with pytest.raises(InvalidAgentTaskEventError):
        service.get("")


def test_get_rejects_blank_event_type_filter():
    service = _service()

    with pytest.raises(InvalidAgentTaskEventError):
        service.get("task-1", event_type="")


def test_get_rejects_invalid_limit():
    service = _service()

    with pytest.raises(InvalidAgentTaskEventError):
        service.get("task-1", limit=-1)


def test_get_limit_zero_returns_empty_list():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)

    assert service.get("task-1", limit=0) == []


def test_get_limit_caps_to_most_recent_entries_oldest_to_newest():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    service.emit("task-1", DEPENDENCY_ADDED)
    service.emit("task-1", READINESS_CHANGED)

    limited = service.get("task-1", limit=2)

    assert [event.event_type for event in limited] == [DEPENDENCY_ADDED, READINESS_CHANGED]


# --- ordering --------------------------------------------------------------------------------


def test_get_is_chronologically_ordered():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    service.emit("task-1", DEPENDENCY_ADDED)
    service.emit("task-1", READINESS_CHANGED)
    service.emit("task-1", CONTEXT_UPDATED)

    events = service.get("task-1")

    assert [event.event_type for event in events] == [
        LIFECYCLE_TRANSITIONED,
        DEPENDENCY_ADDED,
        READINESS_CHANGED,
        CONTEXT_UPDATED,
    ]
    for earlier, later in zip(events, events[1:]):
        assert earlier.occurred_at <= later.occurred_at


# --- event-type filtering ----------------------------------------------------------------------


def test_get_filters_by_event_type():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    service.emit("task-1", DEPENDENCY_ADDED)
    service.emit("task-1", LIFECYCLE_TRANSITIONED)

    filtered = service.get("task-1", event_type=LIFECYCLE_TRANSITIONED)

    assert len(filtered) == 2
    assert all(event.event_type == LIFECYCLE_TRANSITIONED for event in filtered)


def test_get_filter_with_no_matches_returns_empty_list():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)

    assert service.get("task-1", event_type=CONTEXT_UPDATED) == []


# --- latest ------------------------------------------------------------------------------------


def test_latest_returns_most_recent_event():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    latest_event = service.emit("task-1", DEPENDENCY_ADDED)

    assert service.latest("task-1") == latest_event


def test_latest_returns_none_for_task_with_no_events():
    service = _service()

    assert service.latest("does-not-exist") is None


def test_latest_filters_by_event_type():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    latest_dependency_event = service.emit("task-1", DEPENDENCY_ADDED)
    service.emit("task-1", READINESS_CHANGED)

    assert service.latest("task-1", event_type=DEPENDENCY_ADDED) == latest_dependency_event


# --- multiple tasks remain isolated --------------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)
    service.emit("task-1", DEPENDENCY_ADDED)
    service.emit("task-2", LIFECYCLE_TRANSITIONED)

    assert [event.event_type for event in service.get("task-1")] == [LIFECYCLE_TRANSITIONED, DEPENDENCY_ADDED]
    assert [event.event_type for event in service.get("task-2")] == [LIFECYCLE_TRANSITIONED]


# --- append-only behavior ------------------------------------------------------------------------


def test_event_is_frozen():
    event = AgentTaskEvent(task_id="task-1", event_type=LIFECYCLE_TRANSITIONED)

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.event_type = DEPENDENCY_ADDED


def test_events_cannot_mutate_previously_recorded_entries():
    service = _service()
    service.emit("task-1", LIFECYCLE_TRANSITIONED)

    first_read = service.get("task-1")
    first_read.clear()
    first_read.append("garbage")

    second_read = service.get("task-1")
    assert [event.event_type for event in second_read] == [LIFECYCLE_TRANSITIONED]


def test_no_update_or_delete_method_exists():
    service = _service()

    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
    assert not hasattr(service.store, "update")
    assert not hasattr(service.store, "delete")


# --- large/sensitive payload handling ---------------------------------------------------------


def test_payload_secret_values_are_redacted():
    service = _service()

    event = service.emit("task-1", CONTEXT_UPDATED, payload={"note": "api_key: sk-abcdefghijklmnop"})

    assert "sk-abcdefghijklmnop" not in event.payload["note"]
    assert "[REDACTED]" in event.payload["note"]


def test_payload_without_secrets_is_preserved():
    service = _service()

    event = service.emit("task-1", CONTEXT_UPDATED, payload={"source_id": "doc-1", "count": 3})

    assert event.payload == {"source_id": "doc-1", "count": 3}


def test_large_reference_style_payload_is_stored_without_truncation():
    service = _service()
    payload = {"item_ids": [f"item-{i}" for i in range(500)]}

    event = service.emit("task-1", CONTEXT_UPDATED, payload=payload)

    assert len(event.payload["item_ids"]) == 500


# --- JSON persistence ----------------------------------------------------------------------------


def test_json_store_round_trips_events_across_service_instances(tmp_path):
    path = tmp_path / "events.json"

    service_a = LLMAgentTaskEventService(store=JsonAgentTaskEventStore(path))
    service_a.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    service_a.emit("task-1", DEPENDENCY_ADDED)

    service_b = LLMAgentTaskEventService(store=JsonAgentTaskEventStore(path))
    events = service_b.get("task-1")

    assert [event.event_type for event in events] == [LIFECYCLE_TRANSITIONED, DEPENDENCY_ADDED]
    assert events[0].payload == {"to_state": "planned"}
