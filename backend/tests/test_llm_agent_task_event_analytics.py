from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskEventAnalyticsError,
    LLMAgentTaskEventAnalyticsService,
)
from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import CANCELLED, CREATED, FAILED, PLANNED, READY, RUNNING


def _services():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    analytics_service = LLMAgentTaskEventAnalyticsService(query_service=query_service)
    return emitter, query_service, analytics_service


def _at(base, **kwargs):
    return base + timedelta(**kwargs)


# --- normal lifecycle -------------------------------------------------------------------------


def test_normal_lifecycle_analytics():
    emitter, _, analytics_service = _services()
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})

    result = analytics_service.analyze("task-1")

    assert result.task_id == "task-1"
    assert result.event_count == 1
    assert result.event_type_counts == {LIFECYCLE_TRANSITIONED: 1}
    assert result.terminal_outcome is None
    assert result.failure_count == 0


def test_analyze_rejects_blank_task_id():
    _, _, analytics_service = _services()

    with pytest.raises(InvalidAgentTaskEventAnalyticsError):
        analytics_service.analyze("")


# --- multiple state transitions -----------------------------------------------------------------


def test_multiple_state_transitions_are_counted():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})

    result = analytics_service.analyze("task-1")

    assert result.state_transition_counts == {PLANNED: 1, READY: 1, RUNNING: 1}
    assert result.event_count == 4


def test_time_in_state_reports_closed_intervals_only():
    from dataclasses import replace

    emitter, query_service, analytics_service = _services()
    base = datetime.now(timezone.utc) - timedelta(hours=1)

    created = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    query_service.store.delete(created.task_id, created.event_id)
    query_service.store.save(replace(created, occurred_at=base))

    planned = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    query_service.store.delete(planned.task_id, planned.event_id)
    query_service.store.save(replace(planned, occurred_at=_at(base, minutes=5)))

    ready = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    query_service.store.delete(ready.task_id, ready.event_id)
    query_service.store.save(replace(ready, occurred_at=_at(base, minutes=15)))

    result = analytics_service.analyze("task-1")

    assert result.time_in_state[CREATED] == timedelta(minutes=5)
    assert result.time_in_state[PLANNED] == timedelta(minutes=10)
    assert READY not in result.time_in_state  # trailing/open interval never inferred


# --- terminal completion --------------------------------------------------------------------------


def test_terminal_completion_reports_outcome_and_duration():
    from dataclasses import replace

    emitter, query_service, analytics_service = _services()
    base = datetime.now(timezone.utc) - timedelta(hours=1)

    created = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    query_service.store.delete(created.task_id, created.event_id)
    query_service.store.save(replace(created, occurred_at=base))

    planned = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    query_service.store.delete(planned.task_id, planned.event_id)
    query_service.store.save(replace(planned, occurred_at=_at(base, minutes=2)))

    cancelled = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CANCELLED})
    query_service.store.delete(cancelled.task_id, cancelled.event_id)
    query_service.store.save(replace(cancelled, occurred_at=_at(base, minutes=10)))

    result = analytics_service.analyze("task-1")

    assert result.terminal_outcome == CANCELLED
    assert result.time_to_terminal_state == timedelta(minutes=10)


# --- failure ----------------------------------------------------------------------------------------


def test_failure_is_reported_as_terminal_outcome_and_failure_count():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = analytics_service.analyze("task-1")

    assert result.terminal_outcome == FAILED
    assert result.failure_count == 1


def test_non_terminal_stream_has_no_terminal_outcome():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    result = analytics_service.analyze("task-1")

    assert result.terminal_outcome is None
    assert result.time_to_terminal_state is None


# --- retry events --------------------------------------------------------------------------------------


def test_retry_events_are_counted_separately():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", "retry_cancelled")

    result = analytics_service.analyze("task-1")

    assert result.retry_scheduled_count == 2
    assert result.retry_cancelled_count == 1


# --- incomplete event stream ------------------------------------------------------------------------------


def test_incomplete_stream_without_genesis_event_never_infers_duration():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})  # no CREATED ever recorded
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})

    result = analytics_service.analyze("task-1")

    # replay() still assumes CREATED as its own internal starting point (Commit
    # #6's own convention), so both transitions are valid and counted --
    # but with no raw genesis *event* ever recorded, this service refuses to
    # infer any duration relative to a starting point nothing actually marks
    assert result.time_to_first_event is None
    assert result.time_to_terminal_state is None
    assert result.state_transition_counts == {PLANNED: 1, READY: 1}
    # no leading interval before the first observed transition is invented,
    # but the closed interval *between* the two observed transitions is real
    assert set(result.time_in_state) == {PLANNED}


def test_lifecycle_event_missing_to_state_payload_does_not_error():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)  # no payload at all -- legitimate legacy event
    emitter.emit("task-1", DEPENDENCY_ADDED)

    result = analytics_service.analyze("task-1")

    assert result.event_count == 2
    assert result.state_transition_counts == {}
    assert result.time_to_first_event is None


def test_unrecognized_to_state_is_not_counted_as_a_transition():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "not-a-real-state"})

    result = analytics_service.analyze("task-1")

    assert result.state_transition_counts == {}
    assert result.event_count == 1


# --- bounded time range -------------------------------------------------------------------------------------


def test_bounded_time_range_excludes_events_outside_window():
    from dataclasses import replace

    emitter, query_service, analytics_service = _services()
    base = datetime.now(timezone.utc) - timedelta(hours=1)

    first = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    query_service.store.delete(first.task_id, first.event_id)
    query_service.store.save(replace(first, occurred_at=base))

    second = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    query_service.store.delete(second.task_id, second.event_id)
    query_service.store.save(replace(second, occurred_at=_at(base, minutes=5)))

    cutoff = _at(base, minutes=2)
    third = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    query_service.store.delete(third.task_id, third.event_id)
    query_service.store.save(replace(third, occurred_at=_at(base, minutes=20)))

    result = analytics_service.analyze("task-1", start_time=base - timedelta(minutes=1), end_time=cutoff)

    assert result.event_count == 1
    assert result.state_transition_counts == {}


def test_analyze_rejects_non_datetime_bounds():
    from backend.agent_task_events import InvalidAgentTaskEventQueryError

    _, _, analytics_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        analytics_service.analyze("task-1", start_time="not-a-datetime")


# --- empty stream -----------------------------------------------------------------------------------------------


def test_empty_stream_produces_clean_zeroed_result():
    _, _, analytics_service = _services()

    result = analytics_service.analyze("task-1")

    assert result.event_count == 0
    assert result.event_type_counts == {}
    assert result.state_transition_counts == {}
    assert result.first_event_at is None
    assert result.last_event_at is None
    assert result.time_to_first_event is None
    assert result.time_to_terminal_state is None
    assert result.time_in_state == {}
    assert result.retry_scheduled_count == 0
    assert result.retry_cancelled_count == 0
    assert result.failure_count == 0
    assert result.terminal_outcome is None


# --- deterministic repeated analysis -----------------------------------------------------------------------------


def test_repeated_analysis_is_deterministic():
    emitter, _, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", CONTEXT_UPDATED)

    first = analytics_service.analyze("task-1")
    second = analytics_service.analyze("task-1")

    assert first == second


def test_analysis_does_not_mutate_stored_events():
    emitter, query_service, analytics_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    before = query_service.query(task_id="task-1")
    analytics_service.analyze("task-1")
    analytics_service.analyze("task-1")
    after = query_service.query(task_id="task-1")

    assert before == after
