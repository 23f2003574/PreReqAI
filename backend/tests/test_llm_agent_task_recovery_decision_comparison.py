from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_event_analytics import (
    InvalidAgentTaskRecoveryDecisionComparisonError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskRecoveryDecisionAuditService,
    LLMAgentTaskRecoveryDecisionComparisonService,
    LLMAgentTaskRecoveryEffectivenessService,
    LLMAgentTaskRecoveryHistoryService,
    LLMAgentTaskRecoveryOutcomeService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskFailureRecoveryResult,
    AgentTaskRecoveryRecommendation,
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
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(
        history_service=history_service, failure_classifier=classifier
    )
    audit_service = LLMAgentTaskRecoveryDecisionAuditService(event_service=event_service, query_service=query_service)
    comparison_service = LLMAgentTaskRecoveryDecisionComparisonService(
        audit_service=audit_service, history_service=history_service, effectiveness_service=effectiveness_service
    )
    return event_service, outcome_service, audit_service, comparison_service


def _recommendation(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        recommended_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        confidence=0.8,
        reason="context refresh has a strong track record",
        supporting_recovery_ids=(),
        blocking_conditions=(),
        failure_event_id="failure-event-1",
    )
    fields.update(overrides)
    return AgentTaskRecoveryRecommendation(**fields)


def _outcome_result(task_id="task-1", **overrides):
    fields = dict(
        task_id=task_id,
        planned_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        executed_action=RECOVERY_ACTION_REFRESH_CONTEXT,
        success=True,
        failure_reason=None,
        affected_reference="context refreshed",
        source_failure_event_id="failure-event-1",
        partial=False,
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryResult(**fields)


def _illegal_failure(event_service, task_id="task-1"):
    # an illegal CREATED -> FAILED claim: appears as a raw failure candidate
    # (Commit #2's own classifier) but is never validly reached by replay(),
    # so the task's own authoritative state never actually becomes terminal
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _real_terminal_failure(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


# --- recommendation followed successfully --------------------------------------------------------------


def test_recommendation_followed_and_task_recovered():
    event_service, outcome_service, audit_service, comparison_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record(
        "task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True)
    )

    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    assert comparison.was_followed is True
    assert comparison.outcome_status == RECOVERY_OUTCOME_SUCCESS
    assert comparison.was_effective is True
    assert comparison.executed_action == RECOVERY_ACTION_REFRESH_CONTEXT


def test_compare_rejects_blank_task_id():
    _, _, _, comparison_service = _stack()

    with pytest.raises(InvalidAgentTaskRecoveryDecisionComparisonError):
        comparison_service.compare("")


def test_compare_raises_when_no_decision_exists():
    _, _, _, comparison_service = _stack()

    with pytest.raises(InvalidAgentTaskRecoveryDecisionComparisonError):
        comparison_service.compare("task-1")


# --- recommendation followed but recovery failed -------------------------------------------------------------


def test_recommendation_followed_but_execution_failed():
    event_service, outcome_service, audit_service, comparison_service = _stack()
    failing = _real_terminal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record(
        "task-1",
        _outcome_result(
            source_failure_event_id=failing.event_id,
            success=False,
            failure_reason="context store unavailable",
            affected_reference=None,
        ),
    )

    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    assert comparison.was_followed is True
    assert comparison.outcome_status == RECOVERY_OUTCOME_FAILED
    assert comparison.was_effective is False  # task's real terminal state is FAILED


# --- recommendation changed before execution -----------------------------------------------------------------


def test_recommendation_changed_before_execution():
    event_service, outcome_service, audit_service, comparison_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record(
        "task-1",
        _outcome_result(
            source_failure_event_id=failing.event_id,
            planned_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            executed_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
            success=True,
            affected_reference="dead-lettered",
        ),
    )

    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    assert comparison.was_followed is False
    assert comparison.executed_action == RECOVERY_ACTION_MARK_UNRECOVERABLE
    assert "was not followed" in comparison.comparison_reason


# --- no corresponding recovery ----------------------------------------------------------------------------------


def test_no_corresponding_recovery_is_reported_honestly():
    event_service, _, audit_service, comparison_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))

    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    assert comparison.was_followed is None
    assert comparison.outcome_status is None
    assert comparison.was_effective is None
    assert comparison.executed_action is None
    assert "no recovery attempt is recorded" in comparison.comparison_reason


# --- multiple decisions/recoveries ---------------------------------------------------------------------------------


def test_multiple_decisions_each_match_their_own_recovery():
    event_service, outcome_service, audit_service, comparison_service = _stack()
    first_failure = _illegal_failure(event_service)
    second_failure = event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    first_audit = audit_service.record("task-1", _recommendation(failure_event_id=first_failure.event_id))
    second_audit = audit_service.record(
        "task-1", _recommendation(failure_event_id=second_failure.event_id, confidence=0.5)
    )

    outcome_service.record(
        "task-1", _outcome_result(source_failure_event_id=first_failure.event_id, success=True)
    )
    outcome_service.record(
        "task-1",
        _outcome_result(
            source_failure_event_id=second_failure.event_id,
            success=False,
            failure_reason="still not eligible",
            affected_reference=None,
        ),
    )

    first_comparison = comparison_service.compare("task-1", decision_id=first_audit.decision_id)
    second_comparison = comparison_service.compare("task-1", decision_id=second_audit.decision_id)

    assert first_comparison.outcome_status == RECOVERY_OUTCOME_SUCCESS
    assert second_comparison.outcome_status == RECOVERY_OUTCOME_FAILED
    assert first_comparison.decision_id != second_comparison.decision_id


def test_compare_without_decision_id_uses_the_latest_decision():
    event_service, outcome_service, audit_service, comparison_service = _stack()
    failing = _illegal_failure(event_service)
    audit_service.record("task-1", _recommendation(failure_event_id="stale-failure-id", confidence=0.1))
    latest_audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))

    comparison = comparison_service.compare("task-1")

    assert comparison.decision_id == latest_audit.decision_id


# --- insufficient evidence ------------------------------------------------------------------------------------------


def test_insufficient_evidence_when_effectiveness_cannot_determine_terminal_outcome():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    outcome_service = LLMAgentTaskRecoveryOutcomeService(event_service=event_service, query_service=query_service)
    history_service = LLMAgentTaskRecoveryHistoryService(outcome_service=outcome_service)
    effectiveness_service = LLMAgentTaskRecoveryEffectivenessService(history_service=history_service)  # no classifier
    audit_service = LLMAgentTaskRecoveryDecisionAuditService(event_service=event_service, query_service=query_service)
    comparison_service = LLMAgentTaskRecoveryDecisionComparisonService(
        audit_service=audit_service, history_service=history_service, effectiveness_service=effectiveness_service
    )

    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))

    comparison = comparison_service.compare("task-1", decision_id=audit.decision_id)

    assert comparison.was_followed is True
    assert comparison.outcome_status == RECOVERY_OUTCOME_SUCCESS
    assert comparison.was_effective is None
    assert "insufficient evidence" in comparison.comparison_reason


# --- deterministic repeated comparison ------------------------------------------------------------------------------


def test_repeated_comparison_is_deterministic():
    event_service, outcome_service, audit_service, comparison_service = _stack()
    failing = _illegal_failure(event_service)
    audit = audit_service.record("task-1", _recommendation(failure_event_id=failing.event_id))
    outcome_service.record("task-1", _outcome_result(source_failure_event_id=failing.event_id, success=True))

    first = comparison_service.compare("task-1", decision_id=audit.decision_id)
    second = comparison_service.compare("task-1", decision_id=audit.decision_id)

    assert first == second
