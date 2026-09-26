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
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService,
    RECONCILIATION_COMPLETED,
    RECONCILIATION_RESULT_SCHEMA_VERSION,
    RECONCILIATION_UNRESOLVED,
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
        self.results = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService()

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
        return self.results.record(TASK_ID, self.reconciler.reconcile(TASK_ID))


def test_successful_reconciliation_is_persisted_as_completed():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")

    result = f.reconciler.reconcile(TASK_ID)
    record = f.results.record(TASK_ID, result)

    assert record.status == RECONCILIATION_COMPLETED
    assert record.task_id == TASK_ID and record.result_id
    assert record.previous_current_decision_id == "d1"
    assert record.authoritative_decision_id == record.current_decision_id == "d2"
    assert record.changed is True and record.changes == result.changes
    assert record.chain_valid is True
    assert record.reconciled_at == result.reconciled_at
    assert record.schema_version == RECONCILIATION_RESULT_SCHEMA_VERSION


def test_no_op_reconciliation_is_persisted():
    f = _Fixture()
    f.decision("d1", 0)
    f.freshness("d1", 1, status=FRESHNESS_FRESH)
    f.pointer("d1")

    record = f.reconcile_and_record()

    assert record.status == RECONCILIATION_COMPLETED
    assert record.changed is False and record.changes == ()


def test_conflicts_are_persisted_as_unresolved():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("foreign", 1, task_id="task-2")
    f.pointer("foreign")

    result = f.reconciler.reconcile(TASK_ID)
    record = f.results.record(TASK_ID, result)

    assert record.status == RECONCILIATION_UNRESOLVED
    assert record.conflicts == result.conflicts and "foreign" in record.conflicts[0]
    assert record.current_decision_id == "foreign"


def test_unresolved_issues_are_persisted_exactly():
    f = _Fixture()
    f.decision("d1", 0)
    f.freshness("d1", 1, status=FRESHNESS_UNKNOWN, action=REVALIDATION_FAILED)

    result = f.reconciler.reconcile(TASK_ID)
    record = f.results.record(TASK_ID, result)

    assert record.status == RECONCILIATION_UNRESOLVED
    assert record.chain_valid is False
    assert record.unresolved == result.unresolved and record.unresolved
    assert record.authoritative_decision_id is None


def test_duplicate_recording_is_idempotent_and_never_overwrites():
    f = _Fixture()
    f.decision("d1", 0)

    result = f.reconciler.reconcile(TASK_ID)
    first = f.results.record(TASK_ID, result)
    second = f.results.record(TASK_ID, result)
    third = f.results.record(TASK_ID, f.reconciler.reconcile(TASK_ID))

    assert second == first
    assert third.result_id != first.result_id
    assert f.results.get(TASK_ID, first.result_id) == first
    assert [r.result_id for r in f.results.history(TASK_ID)] == [first.result_id, third.result_id]


def test_latest_and_history_retrieval_without_side_effects():
    f = _Fixture()
    assert f.results.latest(TASK_ID) is None and f.results.history(TASK_ID) == []

    f.decision("d1", 0)
    unresolved = f.results.record(TASK_ID, f.reconciler.reconcile(TASK_ID))
    f.freshness("d1", 1, status=FRESHNESS_FRESH)
    completed = f.results.record(TASK_ID, f.reconciler.reconcile(TASK_ID))

    history = f.results.history(TASK_ID)
    assert [r.result_id for r in history] == [unresolved.result_id, completed.result_id]
    assert f.results.latest(TASK_ID) == completed
    assert f.results.history(TASK_ID) == history  # reading is side-effect free
    assert f.results.get("task-2", completed.result_id) is None
    assert f.results.get(TASK_ID, "missing") is None
    assert f.results.history("task-2") == []


def test_records_are_immutable():
    f = _Fixture()
    f.decision("d1", 0)
    record = f.reconcile_and_record()

    with pytest.raises(Exception):
        record.status = RECONCILIATION_UNRESOLVED
    fetched = f.results.get(TASK_ID, record.result_id)
    assert fetched == record and fetched is not record


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    result = f.reconciler.reconcile(TASK_ID)

    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError):
        f.results.record("task-2", result)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError):
        f.results.record(TASK_ID, None)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultError):
        f.results.latest("")
