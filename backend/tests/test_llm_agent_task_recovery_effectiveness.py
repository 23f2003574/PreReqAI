from dataclasses import replace
from datetime import timedelta

import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryEffectivenessError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskRecoveryEffectivenessService,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryOutcomeService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_REPAIR_TASK,
    RECOVERY_ACTION_RETRY,
    AgentTaskFailureRecoveryResult,
)
from backend.agent_task_events import (
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, PLANNED


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(
        history_service=history_service, failure_classifier=classifier
    )
    return event_service, outcome_service, effectiveness_service


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


# --- all-success history --------------------------------------------------------------------------


def test_all_success_history():
    _, outcome_service, effectiveness_service = _stack()
    outcome_service.record("task-1", _result(source_failure_event_id="f-1"))
    outcome_service.record("task-1", _result(source_failure_event_id="f-2"))

    result = effectiveness_service.analyze("task-1")

    assert result.total_attempts == 2
    assert result.successful_attempts == 2
    assert result.failed_attempts == 0
    assert result.success_rate == 1.0


def test_analyze_rejects_blank_task_id():
    _, _, effectiveness_service = _stack()

    with pytest.raises(InvalidAgentTaskRecoveryEffectivenessError):
        effectiveness_service.analyze("")


# --- all-failure history ----------------------------------------------------------------------------


def test_all_failure_history():
    _, outcome_service, effectiveness_service = _stack()
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-1",
            success=False,
            executed_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            planned_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            failure_reason="no dead-letter service",
            affected_reference=None,
        ),
    )

    result = effectiveness_service.analyze("task-1")

    assert result.total_attempts == 1
    assert result.successful_attempts == 0
    assert result.failed_attempts == 1
    assert result.success_rate == 0.0
    assert result.failures_followed_by_success == 0


# --- mixed outcomes ------------------------------------------------------------------------------------


def test_mixed_outcomes_including_partial():
    _, outcome_service, effectiveness_service = _stack()
    outcome_service.record("task-1", _result(source_failure_event_id="f-1", success=True))
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-2",
            success=False,
            failure_reason="scheduler unavailable",
        ),
    )
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-3",
            success=True,
            partial=True,
            planned_action=RECOVERY_ACTION_REPAIR_TASK,
            executed_action=RECOVERY_ACTION_REPAIR_TASK,
            affected_reference="repair applied: final_status=PARTIAL",
        ),
    )

    result = effectiveness_service.analyze("task-1")

    assert result.total_attempts == 3
    assert result.successful_attempts == 1
    assert result.failed_attempts == 1
    assert result.partial_attempts == 1
    assert result.success_rate == pytest.approx(1 / 3)


# --- action-specific success rates ------------------------------------------------------------------------


def test_action_specific_success_rates():
    _, outcome_service, effectiveness_service = _stack()
    outcome_service.record(
        "task-1", _result(source_failure_event_id="f-1", success=True, executed_action=RECOVERY_ACTION_RETRY)
    )
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-2",
            success=False,
            executed_action=RECOVERY_ACTION_RETRY,
            planned_action=RECOVERY_ACTION_RETRY,
            failure_reason="ineligible",
        ),
    )
    outcome_service.record(
        "task-1",
        _result(
            source_failure_event_id="f-3",
            success=True,
            executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
            planned_action=RECOVERY_ACTION_REFRESH_CONTEXT,
            affected_reference="context refreshed: 1 added, 0 removed",
        ),
    )

    result = effectiveness_service.analyze("task-1")

    assert result.attempts_by_action == {RECOVERY_ACTION_RETRY: 2, RECOVERY_ACTION_REFRESH_CONTEXT: 1}
    assert result.success_rate_by_action[RECOVERY_ACTION_RETRY] == 0.5
    assert result.success_rate_by_action[RECOVERY_ACTION_REFRESH_CONTEXT] == 1.0


def test_failures_followed_by_success_counts_distinct_failures():
    _, outcome_service, effectiveness_service = _stack()
    # two attempts against the SAME originating failure -- first fails, second succeeds
    outcome_service.record(
        "task-1",
        _result(source_failure_event_id="f-1", success=False, failure_reason="not yet eligible"),
    )
    outcome_service.record("task-1", _result(source_failure_event_id="f-1", success=True))
    # a second, unrelated failure that never got a successful recovery
    outcome_service.record(
        "task-1",
        _result(source_failure_event_id="f-2", success=False, failure_reason="still failing"),
    )

    result = effectiveness_service.analyze("task-1")

    assert result.failures_followed_by_success == 1


# --- recovery followed by terminal failure -----------------------------------------------------------------


def test_terminal_failure_after_recovery_detected_via_classifier():
    event_service, outcome_service, effectiveness_service = _stack()
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    outcome_service.record(
        "task-1",
        _result(success=False, failure_reason="retry did not help", executed_action=RECOVERY_ACTION_RETRY),
    )

    result = effectiveness_service.analyze("task-1")

    assert result.terminal_failure_after_recovery is True


def test_terminal_failure_after_recovery_false_when_task_did_not_end_in_failure():
    event_service, outcome_service, effectiveness_service = _stack()
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    outcome_service.record("task-1", _result(success=True))

    result = effectiveness_service.analyze("task-1")

    assert result.terminal_failure_after_recovery is False


def test_terminal_failure_after_recovery_is_none_without_classifier():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(history_service=history_service)
    outcome_service.record("task-1", _result())

    result = effectiveness_service.analyze("task-1")

    assert result.terminal_failure_after_recovery is None


# --- incomplete timestamps ------------------------------------------------------------------------------------


def test_incomplete_timestamps_do_not_break_duration_calculation():
    event_service, outcome_service, effectiveness_service = _stack()
    outcome = outcome_service.record("task-1", _result())

    # simulate a legacy/malformed outcome event missing its own timestamp payload keys
    raw_event = [e for e in event_service.get("task-1") if e.event_id == outcome.recovery_id][0]
    corrupted_payload = dict(raw_event.payload)
    corrupted_payload.pop("started_at", None)
    corrupted_payload.pop("completed_at", None)
    event_service.store.delete(raw_event.task_id, raw_event.event_id)
    event_service.store.save(replace(raw_event, payload=corrupted_payload))

    result = effectiveness_service.analyze("task-1")

    assert result.total_attempts == 1
    assert result.average_recovery_duration == timedelta(0)  # falls back to occurred_at for both


# --- empty history ---------------------------------------------------------------------------------------------


def test_empty_history_produces_clean_result():
    _, _, effectiveness_service = _stack()

    result = effectiveness_service.analyze("task-1")

    assert result.total_attempts == 0
    assert result.successful_attempts == 0
    assert result.failed_attempts == 0
    assert result.partial_attempts == 0
    assert result.success_rate is None
    assert result.attempts_by_action == {}
    assert result.success_rate_by_action == {}
    assert result.failures_followed_by_success == 0
    assert result.terminal_failure_after_recovery is None
    assert result.average_recovery_duration is None
    assert result.latest_outcome is None
    assert result.attempts == ()


# --- deterministic repeated analysis -----------------------------------------------------------------------------


def test_repeated_analysis_is_deterministic():
    _, outcome_service, effectiveness_service = _stack()
    outcome_service.record("task-1", _result(source_failure_event_id="f-1"))
    outcome_service.record("task-1", _result(source_failure_event_id="f-2", success=False, failure_reason="oops"))

    first = effectiveness_service.analyze("task-1")
    second = effectiveness_service.analyze("task-1")

    assert first == second


# --- multiple tasks remain isolated -----------------------------------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    _, outcome_service, effectiveness_service = _stack()
    outcome_service.record("task-1", _result(task_id="task-1"))
    outcome_service.record("task-2", _result(task_id="task-2", success=False, failure_reason="oops"))
    outcome_service.record("task-2", _result(task_id="task-2", source_failure_event_id="f-2"))

    result_1 = effectiveness_service.analyze("task-1")
    result_2 = effectiveness_service.analyze("task-2")

    assert result_1.total_attempts == 1
    assert result_2.total_attempts == 2
    assert result_1.success_rate == 1.0
    assert result_2.success_rate == 0.5
