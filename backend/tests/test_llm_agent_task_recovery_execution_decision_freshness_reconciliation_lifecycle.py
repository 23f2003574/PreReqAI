from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    LIFECYCLE_COMPLETED,
    LIFECYCLE_FAILED,
    LIFECYCLE_UNRESOLVED,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _FailingAuditStore(InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore):
    def save(self, record):
        raise RuntimeError("audit store unavailable")


class _Fixture:
    def __init__(self, audit_store=None):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.result_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore()
        self.audit_store = audit_store or InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditStore()
        self.results = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService(store=self.result_store)
        self.audits = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationAuditService(store=self.audit_store)
        self.service = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleService(
            decision_store=self.decision_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.freshness_store
            ),
            chain_index_store=self.index_store, result_service=self.results, audit_service=self.audits,
        )

    def decision(self, decision_id, minutes, verdict=EXECUTION_DECISION_ALLOW, task_id=TASK_ID):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=task_id, snapshot_id="snap", authorization_id="auth-1", decision=verdict,
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

    def counts(self):
        return len(self.results.history(TASK_ID)), len(self.audits.list(TASK_ID))


def test_required_reconciliation_is_performed_persisted_audited_and_verified():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_BLOCK)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")

    result = f.service.reconcile(TASK_ID)

    assert result.status == LIFECYCLE_COMPLETED
    assert result.reconciliation_performed is True
    assert (result.previous_current_decision_id, result.current_decision_id) == ("d1", "d2")
    assert result.authoritative_decision_id == "d2"
    assert f.results.get(TASK_ID, result.result_id) is not None
    assert f.audits.get(result.audit_id).current_decision_id == "d2"
    assert result.final_verification.valid and result.errors == ()
    assert f.decision_store.get("d2").decision == EXECUTION_DECISION_BLOCK


def test_already_consistent_state_is_idempotent():
    f = _Fixture()
    f.decision("d1", 0)
    f.freshness("d1", 1, status=FRESHNESS_FRESH)

    first = f.service.reconcile(TASK_ID)
    counts = f.counts()
    second = f.service.reconcile(TASK_ID)

    assert first.reconciliation_performed and first.status == LIFECYCLE_COMPLETED
    assert second.reconciliation_performed is False and second.status == LIFECYCLE_COMPLETED
    assert second.result_id == first.result_id and second.audit_id is None
    assert second.final_verification.valid
    assert f.counts() == counts == (1, 1)


def test_conflicts_are_unresolved_and_not_guessed():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("foreign", 1, task_id="task-2")
    f.pointer("foreign")

    result = f.service.reconcile(TASK_ID)
    again = f.service.reconcile(TASK_ID)

    assert result.status == LIFECYCLE_UNRESOLVED
    assert result.conflicts and "foreign" in result.conflicts[0]
    assert result.current_decision_id == "foreign"
    assert f.index_store.get(TASK_ID).current_decision_id == "foreign"
    assert again.reconciliation_performed is False and f.counts() == (1, 1)


def test_missing_authoritative_evidence_fails_closed_without_promotion():
    f = _Fixture()
    f.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)
    f.decision("d2", 5, verdict=EXECUTION_DECISION_ALLOW)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.freshness("d2", 7, status=FRESHNESS_UNKNOWN, action=REVALIDATION_FAILED)
    f.pointer("d1")

    result = f.service.reconcile(TASK_ID)

    assert result.status == LIFECYCLE_UNRESOLVED
    assert result.authoritative_decision_id is None
    assert result.current_decision_id == "d1"
    assert f.index_store.get(TASK_ID).current_decision_id == "d1"


def test_failed_prior_verification_triggers_reconciliation():
    f = _Fixture()
    f.decision("d1", 0)
    first = f.service.reconcile(TASK_ID)
    f.decision("d2", 5)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")

    second = f.service.reconcile(TASK_ID)

    assert second.prior_verification.invalid
    assert second.reconciliation_performed is True
    assert second.result_id != first.result_id
    assert second.current_decision_id == "d2" and second.status == LIFECYCLE_COMPLETED


def test_partial_audit_failure_is_reported_as_failed():
    f = _Fixture(audit_store=_FailingAuditStore())
    f.decision("d1", 0)

    result = f.service.reconcile(TASK_ID)

    assert result.status == LIFECYCLE_FAILED
    assert result.result_id is not None and result.audit_id is None
    assert any("audit failed: audit store unavailable" in error for error in result.errors)


def test_persistence_failure_is_reported_as_failed():
    f = _Fixture()
    f.decision("d1", 0)
    f.result_store.save = lambda record: (_ for _ in ()).throw(RuntimeError("disk full"))

    result = f.service.reconcile(TASK_ID)

    assert result.status == LIFECYCLE_FAILED
    assert result.result_id is None and result.final_verification is None
    assert any("disk full" in error for error in result.errors)


def test_repeated_execution_and_history_preservation():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
    f.pointer("d1")
    history = (f.decision_store.history(TASK_ID), f.freshness_store.list_for_task(TASK_ID))

    results = [f.service.reconcile(TASK_ID) for _ in range(3)]

    assert [r.reconciliation_performed for r in results] == [True, False, False]
    assert {r.result_id for r in results} == {results[0].result_id}
    assert f.counts() == (1, 1)
    assert (f.decision_store.history(TASK_ID), f.freshness_store.list_for_task(TASK_ID)) == history


def test_empty_history_fails_closed():
    result = _Fixture().service.reconcile(TASK_ID)

    assert result.status == LIFECYCLE_UNRESOLVED
    assert result.current_decision_id is None and result.authoritative_decision_id is None
    assert any("no decisions are recorded" in issue for issue in result.unresolved)


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleError):
        LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleService().reconcile(task_id)
