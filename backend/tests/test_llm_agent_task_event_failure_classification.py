import pytest

from backend.agent_task_event_analytics import (
    FAILURE_CATEGORY_CONTEXT,
    FAILURE_CATEGORY_DEPENDENCY,
    FAILURE_CATEGORY_EXECUTION,
    FAILURE_CATEGORY_RETRY_EXHAUSTION,
    FAILURE_CATEGORY_TIMEOUT_CANCELLATION,
    FAILURE_CATEGORY_UNKNOWN,
    FAILURE_CATEGORY_VALIDATION_POLICY,
    InvalidAgentTaskEventFailureClassificationError,
    LLMAgentTaskEventFailureClassifier,
)
from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_ADDED,
    DEPENDENCY_REMOVED,
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
    READINESS_CHANGED,
)
from backend.agent_task_lifecycle import CANCELLED, CREATED, FAILED, PLANNED


def _services():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    return emitter, query_service, classifier


# --- normal failures ---------------------------------------------------------------------------


def test_plain_execution_failure_is_classified():
    emitter, _, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    failing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = classifier.classify("task-1")

    assert result.failure_count == 1
    assert result.failures[0].event_id == failing.event_id
    assert result.failures[0].category == FAILURE_CATEGORY_EXECUTION
    assert result.terminal_failure == result.failures[0]


def test_classify_rejects_blank_task_id():
    _, _, classifier = _services()

    with pytest.raises(InvalidAgentTaskEventFailureClassificationError):
        classifier.classify("")


# --- multiple categories -------------------------------------------------------------------------


def test_multiple_categories_across_distinct_tasks():
    emitter, _, classifier = _services()

    emitter.emit("task-1", DEPENDENCY_REMOVED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    emitter.emit("task-2", READINESS_CHANGED)
    emitter.emit("task-2", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    emitter.emit("task-3", CONTEXT_UPDATED)
    emitter.emit("task-3", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    emitter.emit("task-4", LIFECYCLE_TRANSITIONED, payload={"to_state": CANCELLED})

    result_1 = classifier.classify("task-1")
    result_2 = classifier.classify("task-2")
    result_3 = classifier.classify("task-3")
    result_4 = classifier.classify("task-4")

    assert result_1.failures[0].category == FAILURE_CATEGORY_DEPENDENCY
    assert result_2.failures[0].category == FAILURE_CATEGORY_VALIDATION_POLICY
    assert result_3.failures[0].category == FAILURE_CATEGORY_CONTEXT
    assert result_4.failures[0].category == FAILURE_CATEGORY_TIMEOUT_CANCELLATION


def test_category_counts_tally_correctly():
    emitter, _, classifier = _services()
    emitter.emit("task-1", DEPENDENCY_ADDED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = classifier.classify("task-1")

    assert result.category_counts == {FAILURE_CATEGORY_EXECUTION: 1}  # DEPENDENCY_ADDED, not REMOVED


# --- repeated failures --------------------------------------------------------------------------


def test_repeated_failure_claims_all_appear_in_failures():
    emitter, _, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})  # legal path to FAILED
    first = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    second = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})  # reaffirmation

    result = classifier.classify("task-1")

    assert result.failure_count == 2
    assert {f.event_id for f in result.failures} == {first.event_id, second.event_id}
    # replay() only ever validates/records the first one as a real transition
    assert result.terminal_failure.event_id == first.event_id


def test_conflicting_repeated_claim_still_recorded_as_a_failure():
    emitter, _, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})  # legal path to FAILED
    first = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    second = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CANCELLED})  # illegal from FAILED

    result = classifier.classify("task-1")

    assert result.failure_count == 2
    categories = {f.event_id: f.category for f in result.failures}
    assert categories[first.event_id] == FAILURE_CATEGORY_EXECUTION
    assert categories[second.event_id] == FAILURE_CATEGORY_TIMEOUT_CANCELLATION
    assert result.terminal_failure.event_id == first.event_id  # the only one replay() actually validated


# --- retry exhaustion ------------------------------------------------------------------------------


def test_retry_exhaustion_is_detected():
    emitter, _, classifier = _services()
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", "retry_scheduled")
    failing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = classifier.classify("task-1")

    assert result.failures[0].category == FAILURE_CATEGORY_RETRY_EXHAUSTION
    assert "2 retry attempt" in result.failures[0].reason
    assert result.failures[0].event_id == failing.event_id


def test_retry_exhaustion_takes_priority_over_preceding_dependency_signal():
    emitter, _, classifier = _services()
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", DEPENDENCY_REMOVED)  # immediately precedes the failure
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = classifier.classify("task-1")

    assert result.failures[0].category == FAILURE_CATEGORY_RETRY_EXHAUSTION


# --- unknown failures --------------------------------------------------------------------------------


def test_failure_with_no_preceding_event_is_unknown():
    emitter, _, classifier = _services()
    failing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    result = classifier.classify("task-1")

    assert result.failures[0].category == FAILURE_CATEGORY_UNKNOWN
    assert result.failures[0].event_id == failing.event_id


# --- incomplete events -------------------------------------------------------------------------------


def test_lifecycle_event_missing_to_state_payload_is_not_a_failure():
    emitter, _, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED)  # no payload at all -- legitimate legacy event
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"note": "missing to_state"})

    result = classifier.classify("task-1")

    assert result.failure_count == 0
    assert result.failures == ()
    assert result.terminal_failure is None


def test_unrecognized_to_state_is_not_treated_as_a_failure():
    emitter, _, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "not-a-real-state"})

    result = classifier.classify("task-1")

    assert result.failure_count == 0


# --- empty streams ------------------------------------------------------------------------------------


def test_empty_stream_produces_clean_result():
    _, _, classifier = _services()

    result = classifier.classify("task-1")

    assert result.failure_count == 0
    assert result.failures == ()
    assert result.category_counts == {}
    assert result.terminal_failure is None


def test_non_failing_stream_produces_no_failures():
    emitter, _, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CREATED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    result = classifier.classify("task-1")

    assert result.failure_count == 0
    assert result.terminal_failure is None


# --- deterministic output -----------------------------------------------------------------------------


def test_repeated_classification_is_deterministic():
    emitter, _, classifier = _services()
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    first = classifier.classify("task-1")
    second = classifier.classify("task-1")

    assert first == second


def test_classification_does_not_mutate_stored_events():
    emitter, query_service, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    before = query_service.query(task_id="task-1")
    classifier.classify("task-1")
    classifier.classify("task-1")
    after = query_service.query(task_id="task-1")

    assert before == after


def test_bounded_time_range_excludes_events_outside_window():
    from datetime import datetime, timedelta, timezone
    from dataclasses import replace

    emitter, query_service, classifier = _services()
    base = datetime.now(timezone.utc) - timedelta(hours=1)

    early_failure = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    query_service.store.delete(early_failure.task_id, early_failure.event_id)
    query_service.store.save(replace(early_failure, occurred_at=base))

    result = classifier.classify("task-1", start_time=base + timedelta(minutes=1))

    assert result.failure_count == 0
