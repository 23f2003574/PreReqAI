from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _decision(
    decision=EXECUTION_DECISION_ALLOW, created_at=NOW, snapshot_id="snap-1", authorization_id="auth-1",
    blocking_conditions=(), warnings=(), drift_category=None, reconciliation_state=None,
):
    drift = SimpleNamespace(category=drift_category) if drift_category is not None else None
    reconciliation = SimpleNamespace(state=reconciliation_state) if reconciliation_state is not None else None
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=TASK_ID, snapshot_id=snapshot_id, authorization_id=authorization_id, decision=decision,
        reason="test reason", blocking_conditions=blocking_conditions, warnings=warnings,
        validation_result=None, drift_classification=drift, approval_reconciliation=reconciliation,
        created_at=created_at,
    )


def _stack():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    service = LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService(store=store)
    return store, service


def test_identical_decisions_produce_no_change():
    store, service = _stack()
    decision = store.save(_decision())

    result = service.compare(TASK_ID, decision.decision_id, decision.decision_id)

    assert result.changed is False
    assert result.changed_fields == ()
    assert result.decision_transition == "allow -> allow"
    assert result.eligibility_changed is False


def test_allow_to_review_transition():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.decision_transition == "allow -> review"
    assert result.eligibility_changed is True
    assert result.earlier_decision_id == first.decision_id
    assert result.later_decision_id == second.decision_id


def test_review_to_allow_transition():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.decision_transition == "review -> allow"
    assert result.eligibility_changed is True


def test_allow_to_block_transition_is_argument_order_independent():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=1)))

    forward = service.compare(TASK_ID, first.decision_id, second.decision_id)
    backward = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert forward.decision_transition == backward.decision_transition == "allow -> block"
    assert forward.eligibility_changed == backward.eligibility_changed is True


def test_changed_snapshot_is_detected():
    store, service = _stack()
    first = store.save(_decision(snapshot_id="snap-1", created_at=NOW))
    second = store.save(_decision(snapshot_id="snap-2", created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.snapshot_changed is True
    fields = {c.field for c in result.changed_fields}
    assert "snapshot_id" in fields


def test_changed_authorization_is_detected():
    store, service = _stack()
    first = store.save(_decision(authorization_id="auth-1", created_at=NOW))
    second = store.save(_decision(authorization_id="auth-2", created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.authorization_changed is True


def test_changed_approval_reconciliation_is_detected():
    store, service = _stack()
    first = store.save(_decision(reconciliation_state="preserved", created_at=NOW))
    second = store.save(_decision(reconciliation_state="requires_review", created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.approval_reconciliation_changed is True
    fields = {c.field for c in result.changed_fields}
    assert "approval_reconciliation_state" in fields


def test_changed_drift_classification_is_detected():
    store, service = _stack()
    first = store.save(_decision(drift_category="none", created_at=NOW))
    second = store.save(_decision(drift_category="requires_revalidation", created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.drift_classification_changed is True


def test_added_and_removed_blocking_conditions():
    store, service = _stack()
    first = store.save(_decision(blocking_conditions=("dependency unresolved",), created_at=NOW))
    second = store.save(
        _decision(blocking_conditions=("retry not eligible",), created_at=NOW + timedelta(seconds=1))
    )

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.added_blocking_conditions == ("retry not eligible",)
    assert result.removed_blocking_conditions == ("dependency unresolved",)


def test_added_and_removed_warnings():
    store, service = _stack()
    first = store.save(_decision(warnings=("stale plan warning",), created_at=NOW))
    second = store.save(_decision(warnings=("new warning",), created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    assert result.added_warnings == ("new warning",)
    assert result.removed_warnings == ("stale plan warning",)


def test_unchanged_fields_are_excluded_from_changed_fields():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, snapshot_id="snap-1", created_at=NOW))
    second = store.save(
        _decision(decision=EXECUTION_DECISION_REVIEW, snapshot_id="snap-1", created_at=NOW + timedelta(seconds=1))
    )

    result = service.compare(TASK_ID, second.decision_id, first.decision_id)

    fields = {c.field for c in result.changed_fields}
    assert "decision" in fields
    assert "snapshot_id" not in fields
    assert result.snapshot_changed is False


def test_omitting_other_decision_id_uses_previous_decision():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))

    result = service.compare(TASK_ID, second.decision_id)

    assert result.other_decision_id == first.decision_id
    assert result.decision_transition == "allow -> review"


def test_first_ever_decision_has_no_previous_to_compare():
    store, service = _stack()
    only = store.save(_decision())

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError):
        service.compare(TASK_ID, only.decision_id)


def test_missing_decision_raises():
    store, service = _stack()
    existing = store.save(_decision())

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError):
        service.compare(TASK_ID, "never-existed")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError):
        service.compare(TASK_ID, existing.decision_id, "never-existed")


def test_compare_rejects_blank_arguments():
    store, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError):
        service.compare("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError):
        service.compare(TASK_ID, "")
