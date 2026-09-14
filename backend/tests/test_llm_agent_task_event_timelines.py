import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    AgentTaskEventTimeline,
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventTimelineError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
    LLMAgentTaskEventTimelineService,
    READINESS_CHANGED,
)
from backend.agent_task_events.query import InvalidAgentTaskEventQueryError


def _services():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    timeline_service = LLMAgentTaskEventTimelineService(LLMAgentTaskEventQueryService(store=store))
    return emitter, timeline_service


# --- basic build / empty timeline -----------------------------------------------------------


def test_build_returns_timeline_instance():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})

    timeline = timeline_service.build("task-1")

    assert isinstance(timeline, AgentTaskEventTimeline)
    assert timeline.task_id == "task-1"


def test_empty_task_timeline_is_valid():
    _, timeline_service = _services()

    timeline = timeline_service.build("does-not-exist")

    assert timeline.events == ()
    assert timeline.event_count == 0
    assert timeline.first_event_at is None
    assert timeline.last_event_at is None
    assert timeline.event_type_counts == {}
    assert timeline.current_observed_state is None


def test_build_rejects_missing_task_id():
    _, timeline_service = _services()

    with pytest.raises(InvalidAgentTaskEventTimelineError):
        timeline_service.build("")


def test_build_rejects_none_task_id():
    _, timeline_service = _services()

    with pytest.raises(InvalidAgentTaskEventTimelineError):
        timeline_service.build(None)


# --- chronological ordering -----------------------------------------------------------------


def test_timeline_events_are_chronologically_ordered():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", READINESS_CHANGED)

    timeline = timeline_service.build("task-1")

    assert [event.event_type for event in timeline.events] == [
        LIFECYCLE_TRANSITIONED,
        DEPENDENCY_ADDED,
        READINESS_CHANGED,
    ]
    for earlier, later in zip(timeline.events, timeline.events[1:]):
        assert earlier.occurred_at <= later.occurred_at


def test_timeline_deterministic_ordering_for_equal_timestamps():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    timeline_service = LLMAgentTaskEventTimelineService(LLMAgentTaskEventQueryService(store=store))
    same_time = datetime.now(timezone.utc)

    from backend.agent_task_events.models import AgentTaskEvent

    store.save(AgentTaskEvent(task_id="task-1", event_type=DEPENDENCY_ADDED, event_id="b", occurred_at=same_time))
    store.save(AgentTaskEvent(task_id="task-1", event_type=LIFECYCLE_TRANSITIONED, event_id="a", occurred_at=same_time))

    timeline_a = timeline_service.build("task-1")
    timeline_b = timeline_service.build("task-1")

    assert [event.event_id for event in timeline_a.events] == [event.event_id for event in timeline_b.events]
    assert [event.event_id for event in timeline_a.events] == ["a", "b"]  # tie-broken by event_id


# --- event count / type counts --------------------------------------------------------------


def test_timeline_event_count_and_type_counts():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)

    timeline = timeline_service.build("task-1")

    assert timeline.event_count == 3
    assert timeline.event_type_counts == {LIFECYCLE_TRANSITIONED: 2, DEPENDENCY_ADDED: 1}


# --- first / last timestamps ------------------------------------------------------------------


def test_timeline_first_and_last_event_at():
    emitter, timeline_service = _services()
    first = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    last = emitter.emit("task-1", READINESS_CHANGED)

    timeline = timeline_service.build("task-1")

    assert timeline.first_event_at == first.occurred_at
    assert timeline.last_event_at == last.occurred_at


# --- current_observed_state derivation --------------------------------------------------------


def test_current_observed_state_derived_from_lifecycle_events():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "ready"})

    timeline = timeline_service.build("task-1")

    assert timeline.current_observed_state == "ready"


def test_current_observed_state_is_none_without_lifecycle_events():
    emitter, timeline_service = _services()
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", READINESS_CHANGED)

    timeline = timeline_service.build("task-1")

    assert timeline.current_observed_state is None


def test_current_observed_state_ignores_incomplete_lifecycle_events():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)  # no payload at all
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"note": "missing to_state"})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "not-a-real-state"})

    timeline = timeline_service.build("task-1")

    assert timeline.current_observed_state == "planned"  # last *valid* sighting, not invented


# --- time-window filtering ---------------------------------------------------------------------


def test_timeline_time_window_filtering():
    emitter, timeline_service = _services()
    now = datetime.now(timezone.utc)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)

    only_after = timeline_service.build("task-1", start_time=now + timedelta(hours=1))
    everything = timeline_service.build(
        "task-1", start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1)
    )

    assert only_after.event_count == 0
    assert everything.event_count == 2


def test_timeline_rejects_non_datetime_time_bounds():
    _, timeline_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        timeline_service.build("task-1", start_time="not-a-datetime")


# --- multiple tasks remain isolated --------------------------------------------------------------


def test_timeline_multiple_tasks_remain_isolated():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED, payload={"to_state": "ready"})

    timeline_1 = timeline_service.build("task-1")
    timeline_2 = timeline_service.build("task-2")

    assert timeline_1.event_count == 1
    assert timeline_2.event_count == 1
    assert timeline_1.current_observed_state == "planned"
    assert timeline_2.current_observed_state == "ready"


# --- read-only / no duplicated store -------------------------------------------------------------


def test_timeline_service_has_no_mutation_or_emission_methods():
    _, timeline_service = _services()

    assert not hasattr(timeline_service, "emit")
    assert not hasattr(timeline_service, "update")
    assert not hasattr(timeline_service, "delete")
    assert not hasattr(timeline_service, "store")


def test_timeline_is_frozen():
    timeline = AgentTaskEventTimeline(
        task_id="task-1",
        events=(),
        first_event_at=None,
        last_event_at=None,
        event_count=0,
        event_type_counts={},
        current_observed_state=None,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        timeline.event_count = 5


def test_building_timeline_twice_does_not_change_stored_events():
    emitter, timeline_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)

    timeline_service.build("task-1")
    timeline = timeline_service.build("task-1")

    assert timeline.event_count == 1
