from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW, blocking_conditions=(), warnings=()):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=TASK_ID, snapshot_id="snap-1", authorization_id="auth-1", decision=decision,
        reason="test reason", blocking_conditions=blocking_conditions, warnings=warnings,
        validation_result=None, drift_classification=None, approval_reconciliation=None, created_at=created_at,
    )


def _stack():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    comparison_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService(store=store)
    service = LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService(
        store=store, comparison_service=comparison_service
    )
    return store, service


@pytest.mark.parametrize(
    "from_d,to_d,expect_attention",
    [
        (EXECUTION_DECISION_ALLOW, EXECUTION_DECISION_ALLOW, False),
        (EXECUTION_DECISION_ALLOW, EXECUTION_DECISION_REVIEW, True),
        (EXECUTION_DECISION_ALLOW, EXECUTION_DECISION_BLOCK, True),
        (EXECUTION_DECISION_REVIEW, EXECUTION_DECISION_ALLOW, False),
        (EXECUTION_DECISION_REVIEW, EXECUTION_DECISION_REVIEW, False),
        (EXECUTION_DECISION_REVIEW, EXECUTION_DECISION_BLOCK, True),
        (EXECUTION_DECISION_BLOCK, EXECUTION_DECISION_REVIEW, False),
        (EXECUTION_DECISION_BLOCK, EXECUTION_DECISION_ALLOW, False),
        (EXECUTION_DECISION_BLOCK, EXECUTION_DECISION_BLOCK, False),
    ],
)
def test_every_transition_category(from_d, to_d, expect_attention):
    store, service = _stack()
    first = store.save(_decision(decision=from_d, created_at=NOW))
    second = store.save(_decision(decision=to_d, created_at=NOW + timedelta(seconds=1)))

    result = service.analyze(TASK_ID, second.decision_id, first.decision_id)

    assert result.from_decision == from_d
    assert result.to_decision == to_d
    assert result.transition_type == f"{from_d}_to_{to_d}"
    assert result.eligibility_changed == ((from_d == EXECUTION_DECISION_ALLOW) != (to_d == EXECUTION_DECISION_ALLOW))
    assert result.requires_attention is expect_attention


def test_new_blocking_condition_within_same_category_requires_attention():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_REVIEW, blocking_conditions=(), created_at=NOW))
    second = store.save(
        _decision(
            decision=EXECUTION_DECISION_REVIEW, blocking_conditions=("new blocker",),
            created_at=NOW + timedelta(seconds=1),
        )
    )

    result = service.analyze(TASK_ID, second.decision_id, first.decision_id)

    assert result.requires_attention is True
    assert result.blocking_conditions_added == ("new blocker",)
    assert result.blocking_conditions_removed == ()


def test_removed_blocking_conditions_and_warnings_are_reported():
    store, service = _stack()
    first = store.save(
        _decision(blocking_conditions=("old blocker",), warnings=("old warning",), created_at=NOW)
    )
    second = store.save(_decision(created_at=NOW + timedelta(seconds=1)))

    result = service.analyze(TASK_ID, second.decision_id, first.decision_id)

    assert result.blocking_conditions_removed == ("old blocker",)
    assert result.warnings_removed == ("old warning",)


def test_added_warnings_are_reported():
    store, service = _stack()
    first = store.save(_decision(warnings=(), created_at=NOW))
    second = store.save(_decision(warnings=("new warning",), created_at=NOW + timedelta(seconds=1)))

    result = service.analyze(TASK_ID, second.decision_id, first.decision_id)

    assert result.warnings_added == ("new warning",)


def test_unchanged_decisions_produce_no_material_changes():
    store, service = _stack()
    only = store.save(_decision())

    result = service.analyze(TASK_ID, only.decision_id, only.decision_id)

    assert result.material_changes == ()
    assert result.requires_attention is False
    assert result.eligibility_changed is False


def test_defaults_use_latest_and_previous_decision():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=1)))

    result = service.analyze(TASK_ID)

    assert result.from_decision_id == first.decision_id
    assert result.to_decision_id == second.decision_id
    assert result.transition_type == "allow_to_block"


def test_missing_decision_when_no_decisions_recorded():
    store, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError):
        service.analyze(TASK_ID)


def test_missing_previous_decision_raises():
    store, service = _stack()
    only = store.save(_decision())

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError):
        service.analyze(TASK_ID, only.decision_id)


def test_unknown_decision_id_raises():
    store, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError):
        service.analyze(TASK_ID, "never-existed", "also-never-existed")


def test_analyze_rejects_blank_task_id():
    store, service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError):
        service.analyze("")


def test_transition_classification_is_deterministic():
    store, service = _stack()
    first = store.save(_decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW))
    second = store.save(_decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1)))

    result1 = service.analyze(TASK_ID, second.decision_id, first.decision_id)
    result2 = service.analyze(TASK_ID, second.decision_id, first.decision_id)

    assert result1.transition_type == result2.transition_type
    assert result1.requires_attention == result2.requires_attention
    assert result1.material_changes == result2.material_changes
