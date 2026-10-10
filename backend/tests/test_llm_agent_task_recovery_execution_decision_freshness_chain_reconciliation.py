from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.audit_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.service = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(
            decision_store=self.decision_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.audit_store
            ),
            chain_index_store=self.index_store,
        )

    def decision(self, decision_id, minutes, verdict=EXECUTION_DECISION_ALLOW):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id="snap", authorization_id="auth-1", decision=verdict,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )

    def audit(self, decision_id, minutes, status=FRESHNESS_STALE, action=None, replacement=None):
        return self.audit_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=decision_id, freshness_status=status, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=action is not None,
                revalidation_action=action, replacement_decision_id=replacement, recorded_at=_at(minutes),
            )
        )

    def pointer(self, decision_id):
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=(), current_decision_id=decision_id, updated_at=T0,
            )
        )

    def history(self):
        return self.decision_store.history(TASK_ID), self.audit_store.list_for_task(TASK_ID)


def test_already_consistent_state_is_read_only():
    f = _Fixture()
    f.decision("d1", 0)
    f.audit("d1", 1, status=FRESHNESS_FRESH)
    f.pointer("d1")
    index_before = f.index_store.get(TASK_ID)

    result = f.service.reconcile(TASK_ID)

    assert result.changes == () and result.unresolved == () and not result.changed
    assert result.previous_current_decision_id == result.authoritative_latest_decision_id == "d1"
    assert result.current_decision_state == EXECUTION_DECISION_ALLOW
    assert result.final_chain_valid is True
    assert f.index_store.get(TASK_ID) == index_before


def test_stale_pointer_is_advanced_using_transition_rules():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_ALLOW)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_BLOCK)
    f.audit("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")

    result = f.service.reconcile(TASK_ID)

    assert result.previous_current_decision_id == "d1"
    assert result.authoritative_latest_decision_id == result.current_decision_id == "d2"
    assert result.current_decision_state == EXECUTION_DECISION_BLOCK
    assert result.transition.transition_type == "allow_to_block"
    assert result.transition.requires_attention is True
    assert "advanced stale current decision pointer d1 -> d2 (allow_to_block)" in result.changes
    assert f.index_store.get(TASK_ID).current_decision_id == "d2"


def test_missing_pointer_is_initialized_and_dangling_pointer_replaced():
    f = _Fixture()
    f.decision("d1", 0)

    first = f.service.reconcile(TASK_ID)
    assert first.changes == ("set current decision pointer to d1",)

    f.pointer("gone")
    second = f.service.reconcile(TASK_ID)
    assert "references a missing decision" in second.changes[0]
    assert f.index_store.get(TASK_ID).current_decision_id == "d1"


def test_conflicting_pointer_is_reported_not_guessed():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("side", 3, verdict=EXECUTION_DECISION_REVIEW)
    f.decision("d2", 5)
    f.audit("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("side")

    result = f.service.reconcile(TASK_ID)

    # "side" is not linked in, so the chain itself is invalid -- nothing moves.
    assert result.changes == ()
    assert result.current_decision_id == "side"
    assert result.final_chain_valid is False
    assert result.unresolved


def test_pointer_off_a_valid_chain_is_a_conflict():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.audit("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")
    f.service.reconcile(TASK_ID)
    # An existing decision that is not on this task's validated chain.
    f.decision_store.save(
        AgentTaskRecoveryExecutionPreconditionDecision(
            task_id="task-2", snapshot_id="snap", authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
            reason="other", blocking_conditions=(), warnings=(), validation_result=None,
            drift_classification=None, approval_reconciliation=None, created_at=_at(9), decision_id="foreign",
        )
    )
    f.pointer("foreign")

    result = f.service.reconcile(TASK_ID)

    assert result.changes == ()
    assert any("not on the validated chain" in issue for issue in result.unresolved)
    assert f.index_store.get(TASK_ID).current_decision_id == "foreign"


def test_invalid_latest_decision_is_never_made_current():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_ALLOW)
    f.audit("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.audit("d2", 7, status=FRESHNESS_UNKNOWN, action=REVALIDATION_FAILED)
    f.pointer("d1")

    result = f.service.reconcile(TASK_ID)

    assert result.authoritative_latest_decision_id is None
    assert result.current_decision_id == "d1"
    assert result.current_decision_state == EXECUTION_DECISION_REVIEW
    assert result.changes == () and result.final_chain_valid is False
    assert any("last evaluated unknown" in issue for issue in result.unresolved)


def test_empty_history_fails_closed():
    result = _Fixture().service.reconcile(TASK_ID)

    assert result.previous_current_decision_id is None
    assert result.authoritative_latest_decision_id is None
    assert result.current_decision_id is None
    assert result.final_chain_valid is False
    assert any("no decisions are recorded" in issue for issue in result.unresolved)


def test_repeated_reconciliation_is_idempotent_and_preserves_history():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.audit("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")
    history_before = f.history()

    first = f.service.reconcile(TASK_ID)
    second = f.service.reconcile(TASK_ID)

    assert first.changed and not second.changed
    assert second.previous_current_decision_id == second.current_decision_id == "d2"
    assert f.history() == history_before
    assert [d.decision for d in f.decision_store.history(TASK_ID)] == [EXECUTION_DECISION_ALLOW] * 2


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationError):
        LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService().reconcile(task_id)
