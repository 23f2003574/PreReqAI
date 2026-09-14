from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    InvalidAgentTaskEventQueryError,
    JsonAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
    READINESS_CHANGED,
)


def _services():
    from backend.agent_task_events import InMemoryAgentTaskEventStore

    store = InMemoryAgentTaskEventStore()
    return LLMAgentTaskEventService(store=store), LLMAgentTaskEventQueryService(store=store)


# --- task-specific query -------------------------------------------------------------------


def test_query_scoped_to_one_task():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED)

    results = query_service.query(task_id="task-1")

    assert len(results) == 1
    assert results[0].task_id == "task-1"


def test_query_with_no_task_id_spans_every_task():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-2", DEPENDENCY_ADDED)

    results = query_service.query()

    assert {event.task_id for event in results} == {"task-1", "task-2"}


def test_query_rejects_blank_task_id():
    _, query_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        query_service.query(task_id="")


# --- event-type filtering ------------------------------------------------------------------


def test_query_filters_by_event_types():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", READINESS_CHANGED)

    results = query_service.query(task_id="task-1", event_types=[LIFECYCLE_TRANSITIONED, READINESS_CHANGED])

    assert {event.event_type for event in results} == {LIFECYCLE_TRANSITIONED, READINESS_CHANGED}


def test_query_rejects_non_iterable_event_types():
    _, query_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        query_service.query(event_types=123)


def test_query_rejects_blank_event_type_in_list():
    _, query_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        query_service.query(event_types=[LIFECYCLE_TRANSITIONED, ""])


# --- time-range filtering ------------------------------------------------------------------


def test_query_filters_by_time_range():
    emitter, query_service = _services()
    now = datetime.now(timezone.utc)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)

    only_after = query_service.query(task_id="task-1", start_time=now + timedelta(hours=1))
    everything = query_service.query(
        task_id="task-1", start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1)
    )

    assert only_after == []
    assert [event.event_type for event in everything] == [LIFECYCLE_TRANSITIONED, DEPENDENCY_ADDED]


def test_query_rejects_non_datetime_time_bounds():
    _, query_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        query_service.query(start_time="not-a-datetime")

    with pytest.raises(InvalidAgentTaskEventQueryError):
        query_service.query(end_time="not-a-datetime")


# --- combined filters ----------------------------------------------------------------------


def test_query_combines_task_event_type_and_time_filters():
    emitter, query_service = _services()
    now = datetime.now(timezone.utc)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED)

    results = query_service.query(
        task_id="task-1",
        event_types=[LIFECYCLE_TRANSITIONED],
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1),
    )

    assert len(results) == 1
    assert results[0].task_id == "task-1"
    assert results[0].event_type == LIFECYCLE_TRANSITIONED


# --- limit behavior --------------------------------------------------------------------------


def test_query_limit_caps_to_most_recent_entries_oldest_to_newest():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", READINESS_CHANGED)

    limited = query_service.query(task_id="task-1", limit=2)

    assert [event.event_type for event in limited] == [DEPENDENCY_ADDED, READINESS_CHANGED]


def test_query_limit_zero_returns_empty_list():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)

    assert query_service.query(task_id="task-1", limit=0) == []


def test_query_rejects_negative_limit():
    _, query_service = _services()

    with pytest.raises(InvalidAgentTaskEventQueryError):
        query_service.query(limit=-1)


# --- empty / no-match results ----------------------------------------------------------------


def test_query_missing_task_returns_empty_list():
    _, query_service = _services()

    assert query_service.query(task_id="does-not-exist") == []


def test_query_no_matching_event_type_returns_empty_list():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)

    assert query_service.query(task_id="task-1", event_types=[CONTEXT_UPDATED]) == []


def test_query_with_no_events_at_all_returns_empty_list():
    _, query_service = _services()

    assert query_service.query() == []


# --- ordering is preserved -------------------------------------------------------------------


def test_query_results_are_chronologically_ordered():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", READINESS_CHANGED)

    results = query_service.query(task_id="task-1")

    for earlier, later in zip(results, results[1:]):
        assert earlier.occurred_at <= later.occurred_at


# --- multiple tasks remain isolated ------------------------------------------------------------


def test_query_multiple_tasks_remain_isolated_when_scoped():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED)

    assert len(query_service.query(task_id="task-1")) == 2
    assert len(query_service.query(task_id="task-2")) == 1


# --- count -------------------------------------------------------------------------------------


def test_count_matches_query_length():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED)

    assert query_service.count() == len(query_service.query())
    assert query_service.count(task_id="task-1") == len(query_service.query(task_id="task-1"))
    assert query_service.count(event_types=[LIFECYCLE_TRANSITIONED]) == len(
        query_service.query(event_types=[LIFECYCLE_TRANSITIONED])
    )


def test_count_zero_when_nothing_matches():
    _, query_service = _services()

    assert query_service.count(task_id="does-not-exist") == 0


# --- read-only: never mutates or emits ----------------------------------------------------------


def test_query_service_has_no_mutation_or_emission_methods():
    _, query_service = _services()

    assert not hasattr(query_service, "emit")
    assert not hasattr(query_service, "update")
    assert not hasattr(query_service, "delete")


def test_querying_does_not_change_stored_events():
    emitter, query_service = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)

    query_service.query(task_id="task-1")
    query_service.query(task_id="task-1")

    assert query_service.count(task_id="task-1") == 1


# --- JSON persistence ----------------------------------------------------------------------------


def test_query_reads_through_json_store(tmp_path):
    path = tmp_path / "events.json"
    store = JsonAgentTaskEventStore(path)
    emitter = LLMAgentTaskEventService(store=store)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    emitter.emit("task-2", DEPENDENCY_ADDED)

    query_service = LLMAgentTaskEventQueryService(store=JsonAgentTaskEventStore(path))

    assert query_service.count() == 2
    assert len(query_service.query(task_id="task-1")) == 1
