import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryOutcomeError,
    LLMAgentTaskRecoveryOutcomeService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_REPAIR_TASK,
    RECOVERY_ACTION_RETRY,
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_PARTIAL,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskFailureRecoveryResult,
)
from backend.agent_task_events import (
    CONTEXT_UPDATED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)


def _services():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    return event_service, outcome_service


def _result(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        planned_action=RECOVERY_ACTION_RETRY,
        executed_action=RECOVERY_ACTION_RETRY,
        success=True,
        failure_reason=None,
        affected_reference="retry scheduled: attempt 1",
        source_failure_event_id="failure-event-1",
        partial=False,
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryResult(**fields)


# --- successful outcome --------------------------------------------------------------------------


def test_successful_outcome_is_recorded():
    _, outcome_service = _services()

    outcome = outcome_service.record("task-1", _result())

    assert outcome.task_id == "task-1"
    assert outcome.status == RECOVERY_OUTCOME_SUCCESS
    assert outcome.planned_action == RECOVERY_ACTION_RETRY
    assert outcome.executed_action == RECOVERY_ACTION_RETRY
    assert outcome.reason == "retry scheduled: attempt 1"
    assert outcome.started_at == outcome.completed_at


def test_record_rejects_blank_task_id():
    _, outcome_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryOutcomeError):
        outcome_service.record("", _result())


def test_record_rejects_non_result_argument():
    _, outcome_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryOutcomeError):
        outcome_service.record("task-1", "not-a-result")


def test_record_rejects_task_id_mismatch():
    _, outcome_service = _services()

    with pytest.raises(InvalidAgentTaskRecoveryOutcomeError):
        outcome_service.record("task-2", _result(task_id="task-1"))


# --- failed outcome ---------------------------------------------------------------------------------


def test_failed_outcome_is_recorded():
    _, outcome_service = _services()
    failed_result = _result(
        success=False,
        executed_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
        planned_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
        failure_reason="no dead-letter service was supplied",
        affected_reference=None,
    )

    outcome = outcome_service.record("task-1", failed_result)

    assert outcome.status == RECOVERY_OUTCOME_FAILED
    assert outcome.reason == "no dead-letter service was supplied"


# --- partial outcome where supported ------------------------------------------------------------------


def test_partial_outcome_is_recorded():
    _, outcome_service = _services()
    partial_result = _result(
        planned_action=RECOVERY_ACTION_REPAIR_TASK,
        executed_action=RECOVERY_ACTION_REPAIR_TASK,
        success=True,
        partial=True,
        affected_reference="repair applied: final_status=PARTIAL",
    )

    outcome = outcome_service.record("task-1", partial_result)

    assert outcome.status == RECOVERY_OUTCOME_PARTIAL


# --- source failure linkage ------------------------------------------------------------------------------


def test_source_failure_event_id_is_linked():
    _, outcome_service = _services()

    outcome = outcome_service.record("task-1", _result(source_failure_event_id="failure-event-99"))

    assert outcome.source_failure_event_id == "failure-event-99"


def test_missing_source_failure_event_id_is_preserved_as_none():
    _, outcome_service = _services()

    outcome = outcome_service.record("task-1", _result(source_failure_event_id=None))

    assert outcome.source_failure_event_id is None


# --- duplicate recording/idempotency ------------------------------------------------------------------------


def test_duplicate_recording_returns_existing_outcome():
    _, outcome_service = _services()
    result = _result()

    first = outcome_service.record("task-1", result)
    second = outcome_service.record("task-1", result)

    assert first == second
    assert len(outcome_service.list("task-1")) == 1


def test_distinct_outcomes_for_the_same_task_are_both_recorded():
    _, outcome_service = _services()
    first_result = _result(source_failure_event_id="failure-1")
    second_result = _result(source_failure_event_id="failure-2")

    outcome_service.record("task-1", first_result)
    outcome_service.record("task-1", second_result)

    assert len(outcome_service.list("task-1")) == 2


# --- retrieval / list ordering ---------------------------------------------------------------------------------


def test_list_returns_outcomes_oldest_to_newest():
    _, outcome_service = _services()
    first = outcome_service.record("task-1", _result(source_failure_event_id="failure-1"))
    second = outcome_service.record("task-1", _result(source_failure_event_id="failure-2"))

    outcomes = outcome_service.list("task-1")

    assert [o.recovery_id for o in outcomes] == [first.recovery_id, second.recovery_id]


def test_get_without_recovery_id_returns_the_latest_outcome():
    _, outcome_service = _services()
    outcome_service.record("task-1", _result(source_failure_event_id="failure-1"))
    latest = outcome_service.record("task-1", _result(source_failure_event_id="failure-2"))

    assert outcome_service.get("task-1") == latest


def test_get_with_recovery_id_returns_the_matching_outcome():
    _, outcome_service = _services()
    first = outcome_service.record("task-1", _result(source_failure_event_id="failure-1"))
    outcome_service.record("task-1", _result(source_failure_event_id="failure-2"))

    assert outcome_service.get("task-1", recovery_id=first.recovery_id) == first


def test_repeated_list_is_deterministic():
    _, outcome_service = _services()
    outcome_service.record("task-1", _result(source_failure_event_id="failure-1"))
    outcome_service.record("task-1", _result(source_failure_event_id="failure-2"))

    assert outcome_service.list("task-1") == outcome_service.list("task-1")


# --- missing task/recovery reference ------------------------------------------------------------------------------


def test_get_returns_none_for_unknown_task():
    _, outcome_service = _services()

    assert outcome_service.get("does-not-exist") is None


def test_get_returns_none_for_unknown_recovery_id():
    _, outcome_service = _services()
    outcome_service.record("task-1", _result())

    assert outcome_service.get("task-1", recovery_id="does-not-exist") is None


def test_list_returns_empty_list_for_unknown_task():
    _, outcome_service = _services()

    assert outcome_service.list("does-not-exist") == []


# --- original event remains unchanged ------------------------------------------------------------------------------


def test_original_failure_event_remains_unchanged():
    event_service, outcome_service = _services()
    failure_event = event_service.emit("task-1", CONTEXT_UPDATED, payload={"detail": "original"})

    before = event_service.get("task-1")
    outcome_service.record("task-1", _result(source_failure_event_id=failure_event.event_id))
    after_ids = {e.event_id for e in event_service.get("task-1")}

    # the original failure event still exists, byte-for-byte unchanged
    matching_before = [e for e in before if e.event_id == failure_event.event_id][0]
    matching_after = [e for e in event_service.get("task-1") if e.event_id == failure_event.event_id][0]
    assert matching_before == matching_after
    assert failure_event.event_id in after_ids


def test_recording_does_not_remove_or_mutate_other_events():
    event_service, outcome_service = _services()
    event_service.emit("task-1", CONTEXT_UPDATED)

    before_count = len(event_service.get("task-1"))
    outcome_service.record("task-1", _result())
    after_count = len(event_service.get("task-1"))

    assert after_count == before_count + 1  # only the new outcome event was added
