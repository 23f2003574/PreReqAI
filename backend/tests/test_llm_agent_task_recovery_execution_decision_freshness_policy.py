from datetime import datetime, timezone

from backend.agent_task_recovery_execution_precondition_snapshots import (
    DRIFT_EXECUTION_BLOCKED,
    DRIFT_NON_BLOCKING,
    DRIFT_NONE,
    EXECUTION_DECISION_ALLOW,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    AgentTaskRecoveryExecutionCurrentStateEvidence,
    AgentTaskRecoveryExecutionPreconditionDecision,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _decision(snapshot_id="snap-1"):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id="task-1", snapshot_id=snapshot_id, authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
        reason="test reason", blocking_conditions=(), warnings=(), validation_result=None,
        drift_classification=None, approval_reconciliation=None, created_at=NOW, decision_id="decision-1",
    )


def _evidence(current_state_version="snap-1", drift_category=DRIFT_NONE, ambiguous=False):
    return AgentTaskRecoveryExecutionCurrentStateEvidence(
        current_state_version=current_state_version, drift_category=drift_category, ambiguous=ambiguous
    )


def test_matching_version_and_no_drift_is_fresh():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision()

    result = policy.explain(decision, _evidence(current_state_version="snap-1", drift_category=DRIFT_NONE))

    assert result.status == FRESHNESS_FRESH
    assert policy.is_fresh(decision, _evidence(current_state_version="snap-1", drift_category=DRIFT_NONE)) is True


def test_equivalent_non_blocking_drift_is_still_fresh():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision()

    result = policy.explain(decision, _evidence(current_state_version="snap-1", drift_category=DRIFT_NON_BLOCKING))

    assert result.status == FRESHNESS_FRESH


def test_changed_version_is_stale():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision(snapshot_id="snap-1")

    result = policy.explain(decision, _evidence(current_state_version="snap-2"))

    assert result.status == FRESHNESS_STALE
    assert result.decision_state_version == "snap-1"
    assert result.current_state_version == "snap-2"


def test_blocking_drift_without_version_change_is_stale():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision()

    result = policy.explain(
        decision, _evidence(current_state_version="snap-1", drift_category=DRIFT_EXECUTION_BLOCKED)
    )

    assert result.status == FRESHNESS_STALE


def test_missing_version_is_indeterminate_not_fresh():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision()

    result = policy.explain(decision, _evidence(current_state_version=None))

    assert result.status == FRESHNESS_UNKNOWN
    assert policy.is_fresh(decision, _evidence(current_state_version=None)) is False


def test_ambiguous_evidence_is_indeterminate_even_with_matching_version():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision()

    result = policy.explain(decision, _evidence(current_state_version="snap-1", ambiguous=True))

    assert result.status == FRESHNESS_UNKNOWN
    assert policy.is_fresh(decision, _evidence(current_state_version="snap-1", ambiguous=True)) is False


def test_explain_result_echoes_decision_identity():
    policy = LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy()
    decision = _decision()

    result = policy.explain(decision, _evidence())

    assert result.task_id == decision.task_id
    assert result.decision_id == decision.decision_id
    assert result.decision_timestamp == decision.created_at
