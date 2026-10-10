from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
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
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.reconciler = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(
            decision_store=self.decision_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.freshness_store
            ),
            chain_index_store=self.index_store,
        )
        self.audit = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService()

    def decision(self, decision_id, minutes, task_id=TASK_ID):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=task_id, snapshot_id="snap", authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )

    def freshness(self, decision_id, minutes, status=FRESHNESS_STALE, action=None, replacement=None):
        return self.freshness_store.save(
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

    def reconcile_and_record(self):
        return self.audit.record(TASK_ID, self.reconciler.reconcile(TASK_ID))


def test_no_op_reconciliation_is_recorded():
    f = _Fixture()
    f.decision("d1", 0)
    f.freshness("d1", 1, status=FRESHNESS_FRESH)
    f.pointer("d1")

    record = f.reconcile_and_record()

    assert record.changed is False and record.changes == ()
    assert record.previous_current_decision_id == record.authoritative_decision_id == "d1"
    assert record.chain_valid is True and record.conflicts == () and record.unresolved == ()
    assert f.audit.list(TASK_ID) == [record]


def test_successful_reconciliation_captures_the_pointer_change():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")

    result = f.reconciler.reconcile(TASK_ID)
    record = f.audit.record(TASK_ID, result)

    assert record.changed is True
    assert record.previous_current_decision_id == "d1"
    assert record.authoritative_decision_id == record.current_decision_id == "d2"
    assert record.changes == result.changes
    assert record.reconciled_at == result.reconciled_at
    assert f.audit.get(record.audit_id) == record


def test_conflict_is_preserved_exactly():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("foreign", 1, task_id="task-2")
    f.pointer("foreign")

    result = f.reconciler.reconcile(TASK_ID)
    record = f.audit.record(TASK_ID, result)

    assert record.conflicts == result.conflicts
    assert len(record.conflicts) == 1 and "foreign" in record.conflicts[0]
    assert record.changed is False
    assert record.current_decision_id == "foreign"


def test_invalid_chain_is_recorded_with_its_unresolved_issues():
    f = _Fixture()
    f.decision("d1", 0)
    f.freshness("d1", 1, status=FRESHNESS_UNKNOWN, action=REVALIDATION_FAILED)

    result = f.reconciler.reconcile(TASK_ID)
    record = f.audit.record(TASK_ID, result)

    assert record.chain_valid is False
    assert record.authoritative_decision_id is None
    assert record.unresolved == result.unresolved and record.unresolved


def test_duplicate_recording_of_the_same_operation_is_idempotent():
    f = _Fixture()
    f.decision("d1", 0)

    result = f.reconciler.reconcile(TASK_ID)
    first = f.audit.record(TASK_ID, result)
    second = f.audit.record(TASK_ID, result)
    later_noop = f.audit.record(TASK_ID, f.reconciler.reconcile(TASK_ID))

    assert second == first
    assert later_noop.audit_id != first.audit_id
    assert [r.audit_id for r in f.audit.list(TASK_ID)] == [first.audit_id, later_noop.audit_id]


def test_recording_preserves_decision_and_audit_history():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    before = (f.decision_store.history(TASK_ID), f.freshness_store.list_for_task(TASK_ID))
    result = f.reconciler.reconcile(TASK_ID)
    index_after_reconcile = f.index_store.get(TASK_ID)

    f.audit.record(TASK_ID, result)
    f.audit.record(TASK_ID, result)

    assert (f.decision_store.history(TASK_ID), f.freshness_store.list_for_task(TASK_ID)) == before
    assert f.index_store.get(TASK_ID) == index_after_reconcile


def test_result_for_another_task_is_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    result = f.reconciler.reconcile(TASK_ID)

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError):
        f.audit.record("task-2", result)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError):
        f.audit.record(TASK_ID, None)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditError):
        f.audit.record("", replace(result, task_id=""))
