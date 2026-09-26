from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    RESOLUTION_CONFLICT,
    RESOLUTION_REJECTED,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
            store=InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        )
        common = dict(
            decision_store=self.decision_store, freshness_audit_service=self.audit_service,
            chain_index_store=self.index_store,
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        self.reconciler = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common)
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=self.supersession_store, **common
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

    def raw(self, old, new):
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=EXECUTION_DECISION_ALLOW, replacement_decision=EXECUTION_DECISION_ALLOW,
                reason="r", recorded_at=T0,
            )
        )


def test_single_decision_resolves_to_itself():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_RESOLVED
    assert result.terminal_decision_id == "d1" and result.terminal_decision == EXECUTION_DECISION_REVIEW
    assert result.chain == ("d1",) and result.superseded_decision_ids == ()
    assert result.issues == ()


def test_linear_chain_resolves_terminal_and_keeps_its_verdict():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_REVIEW)
    f.decision("d3", 10, verdict=EXECUTION_DECISION_BLOCK)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    f.supersession.supersede(TASK_ID, "d2", "d3", "revalidated")
    f.reconciler.reconcile(TASK_ID)  # sets the authoritative pointer to d3

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_RESOLVED
    assert result.terminal_decision_id == "d3" and result.terminal_decision == EXECUTION_DECISION_BLOCK
    assert result.chain == ("d1", "d2", "d3")
    assert result.superseded_decision_ids == ("d1", "d2")
    assert result.reconciled_pointer == "d3"


def test_conflicting_successors_are_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.raw("d1", "d2")
    f.raw("d1", "d3")

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_REJECTED
    assert result.terminal_decision_id is None and result.superseded_decision_ids == ()
    assert any("conflicting successors" in issue for issue in result.issues)


def test_cycle_is_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d2", "d1")

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_REJECTED
    assert any("cyclic" in issue for issue in result.issues)


def test_missing_decision_is_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    f.raw("d1", "gone")

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_REJECTED
    assert any("gone does not exist" in issue for issue in result.issues)


def test_newer_unlinked_decision_is_not_inferred_as_replacement():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_BLOCK)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_ALLOW)  # newer, but never superseding d1

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_REJECTED
    assert result.terminal_decision_id is None and result.terminal_decision is None
    assert any("ambiguous" in issue for issue in result.issues)


def test_pointer_mismatch_is_a_conflict_not_a_guess():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    index = f.index_store.get(TASK_ID)
    f.index_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
            task_id=TASK_ID, links=index.links, current_decision_id="d1", updated_at=T0,
        )
    )

    result = f.service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_CONFLICT
    assert result.terminal_decision_id is None
    assert result.chain == ("d1", "d2") and result.reconciled_pointer == "d1"
    assert "disagrees with the supersession terminal d2" in result.issues[0]


def test_empty_history_is_rejected():
    result = _Fixture().service.resolve(TASK_ID)

    assert result.resolution_state == RESOLUTION_REJECTED
    assert result.chain == () and result.terminal_decision_id is None


def test_repeated_resolution_is_deterministic_and_read_only():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID))

    first = f.service.resolve(TASK_ID)
    second = f.service.resolve(TASK_ID)

    assert first == second and first.terminal_decision_id == "d2"
    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID),
    )


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService().resolve(task_id)
