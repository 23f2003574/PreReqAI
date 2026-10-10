import pytest

from backend.agent_task_events import (
    AgentTaskEvent,
    CONTEXT_UPDATED,
    CORRELATION_ESTABLISHED,
    DEPENDENCY_ADDED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventCorrelationError,
    InvalidAgentTaskEventError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventCorrelationService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)


def _services():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    correlation_service = LLMAgentTaskEventCorrelationService(emitter)
    return emitter, correlation_service


# --- extended emit() accepts correlation metadata -------------------------------------------


def test_emit_accepts_correlation_metadata():
    emitter, _ = _services()

    event = emitter.emit(
        "task-1",
        LIFECYCLE_TRANSITIONED,
        correlation_id="corr-1",
        parent_event_id="event-0",
        operation_id="op-1",
    )

    assert event.correlation_id == "corr-1"
    assert event.parent_event_id == "event-0"
    assert event.operation_id == "op-1"


def test_emit_defaults_correlation_metadata_to_none():
    emitter, _ = _services()

    event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)

    assert event.correlation_id is None
    assert event.parent_event_id is None
    assert event.operation_id is None


def test_emit_rejects_blank_correlation_id():
    emitter, _ = _services()

    with pytest.raises(InvalidAgentTaskEventError):
        emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="")


def test_emit_rejects_non_string_parent_event_id():
    emitter, _ = _services()

    with pytest.raises(InvalidAgentTaskEventError):
        emitter.emit("task-1", LIFECYCLE_TRANSITIONED, parent_event_id=123)


# --- existing serialization compatibility ----------------------------------------------------


def test_uncorrelated_legacy_event_round_trips_through_json(tmp_path):
    from backend.agent_task_events import JsonAgentTaskEventStore

    path = tmp_path / "events.json"
    store = JsonAgentTaskEventStore(path)
    emitter = LLMAgentTaskEventService(store=store)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)  # no correlation metadata at all

    reloaded = JsonAgentTaskEventStore(path).list_for_task("task-1")

    assert len(reloaded) == 1
    assert reloaded[0].correlation_id is None
    assert reloaded[0].parent_event_id is None
    assert reloaded[0].operation_id is None


def test_legacy_event_dict_without_correlation_keys_still_loads():
    legacy_dict = {
        "task_id": "task-1",
        "event_type": LIFECYCLE_TRANSITIONED,
        "payload": None,
        "event_id": "legacy-1",
        "occurred_at": "2026-01-01T00:00:00+00:00",
    }

    event = AgentTaskEvent.from_dict(legacy_dict)

    assert event.correlation_id is None
    assert event.parent_event_id is None
    assert event.operation_id is None


def test_uncorrelated_legacy_events_remain_queryable():
    emitter, correlation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)

    query_service = LLMAgentTaskEventQueryService(store=emitter.store)
    events = query_service.query(task_id="task-1")

    assert len(events) == 2
    assert correlation_service.get_related("corr-does-not-exist") == []


# --- correlate() / get_related() ---------------------------------------------------------------


def test_correlate_emits_marker_event_with_correlation_id():
    _, correlation_service = _services()

    event = correlation_service.correlate("task-1", "corr-1")

    assert isinstance(event, AgentTaskEvent)
    assert event.task_id == "task-1"
    assert event.event_type == CORRELATION_ESTABLISHED
    assert event.correlation_id == "corr-1"


def test_events_share_a_correlation_id():
    emitter, correlation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-1")
    emitter.emit("task-2", DEPENDENCY_ADDED, correlation_id="corr-1")
    emitter.emit("task-3", CONTEXT_UPDATED, correlation_id="corr-2")

    related = correlation_service.get_related("corr-1")

    assert {event.task_id for event in related} == {"task-1", "task-2"}
    assert all(event.correlation_id == "corr-1" for event in related)


def test_get_related_returns_only_matching_events():
    emitter, correlation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-1")
    emitter.emit("task-1", DEPENDENCY_ADDED, correlation_id="corr-2")
    emitter.emit("task-1", CONTEXT_UPDATED)  # uncorrelated

    related = correlation_service.get_related("corr-1")

    assert len(related) == 1
    assert related[0].event_type == LIFECYCLE_TRANSITIONED


def test_get_related_returns_empty_list_for_unknown_correlation_id():
    _, correlation_service = _services()

    assert correlation_service.get_related("does-not-exist") == []


def test_get_related_rejects_blank_correlation_id():
    _, correlation_service = _services()

    with pytest.raises(InvalidAgentTaskEventCorrelationError):
        correlation_service.get_related("")


def test_correlate_rejects_blank_correlation_id():
    _, correlation_service = _services()

    with pytest.raises(InvalidAgentTaskEventCorrelationError):
        correlation_service.correlate("task-1", "")


def test_correlate_propagates_underlying_task_id_error():
    _, correlation_service = _services()

    with pytest.raises(InvalidAgentTaskEventError):
        correlation_service.correlate("", "corr-1")


# --- get_children() / parent-child resolution -------------------------------------------------


def test_parent_child_relationships_resolve_correctly():
    emitter, correlation_service = _services()
    root = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    child_a = emitter.emit("task-1", DEPENDENCY_ADDED, parent_event_id=root.event_id)
    child_b = emitter.emit("task-2", CONTEXT_UPDATED, parent_event_id=root.event_id)
    emitter.emit("task-1", "readiness_changed")  # unrelated, no parent

    children = correlation_service.get_children(root.event_id)

    assert {event.event_id for event in children} == {child_a.event_id, child_b.event_id}


def test_get_children_returns_empty_list_for_event_with_no_children():
    emitter, correlation_service = _services()
    event = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)

    assert correlation_service.get_children(event.event_id) == []


def test_get_children_returns_empty_list_for_unknown_event_id():
    _, correlation_service = _services()

    assert correlation_service.get_children("does-not-exist") == []


def test_get_children_rejects_blank_event_id():
    _, correlation_service = _services()

    with pytest.raises(InvalidAgentTaskEventCorrelationError):
        correlation_service.get_children("")


# --- multiple tasks/correlations remain isolated ------------------------------------------------


def test_multiple_correlations_remain_isolated():
    emitter, correlation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-1")
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED, correlation_id="corr-2")

    assert len(correlation_service.get_related("corr-1")) == 1
    assert len(correlation_service.get_related("corr-2")) == 1


def test_multiple_parents_remain_isolated():
    emitter, correlation_service = _services()
    parent_a = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    parent_b = emitter.emit("task-2", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED, parent_event_id=parent_a.event_id)
    emitter.emit("task-2", DEPENDENCY_ADDED, parent_event_id=parent_b.event_id)

    assert len(correlation_service.get_children(parent_a.event_id)) == 1
    assert len(correlation_service.get_children(parent_b.event_id)) == 1


# --- correlation does not alter ordering or payload semantics -----------------------------------


def test_correlated_events_preserve_chronological_order():
    emitter, correlation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-1")
    emitter.emit("task-2", DEPENDENCY_ADDED, correlation_id="corr-1")
    emitter.emit("task-1", CONTEXT_UPDATED, correlation_id="corr-1")

    related = correlation_service.get_related("corr-1")

    for earlier, later in zip(related, related[1:]):
        assert earlier.occurred_at <= later.occurred_at


def test_correlation_does_not_duplicate_or_alter_payload():
    emitter, correlation_service = _services()
    original_payload = {"source_id": "doc-1"}
    emitter.emit("task-1", CONTEXT_UPDATED, payload=original_payload, correlation_id="corr-1")

    related = correlation_service.get_related("corr-1")

    assert related[0].payload == original_payload


def test_correlate_marker_event_carries_no_payload():
    _, correlation_service = _services()

    event = correlation_service.correlate("task-1", "corr-1")

    assert event.payload is None


# --- read-only guarantees ------------------------------------------------------------------------


def test_get_related_and_get_children_do_not_mutate_store():
    emitter, correlation_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, correlation_id="corr-1")

    correlation_service.get_related("corr-1")
    correlation_service.get_children("does-not-exist")

    assert len(emitter.get("task-1")) == 1
