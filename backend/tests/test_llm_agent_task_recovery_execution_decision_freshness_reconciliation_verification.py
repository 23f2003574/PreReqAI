from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    INTEGRITY_INVALID,
    RECONCILIATION_COMPLETED,
    RECONCILIATION_VERIFICATION_INVALID,
    RECONCILIATION_VERIFICATION_VALID,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore,
    InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self, integrity_service=None):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.result_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultRawStore()
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        validation = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
            decision_store=self.decision_store, freshness_audit_service=audit_service,
            chain_index_store=self.index_store,
        )
        self.reconciler = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(
            decision_store=self.decision_store, freshness_audit_service=audit_service,
            chain_index_store=self.index_store, chain_validation_service=validation,
        )
        self.results = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService(
            store=self.result_store
        )
        self.verifier = LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService(
            result_service=self.results, decision_store=self.decision_store,
            chain_validation_service=validation, integrity_service=integrity_service,
        )

    def decision(self, decision_id, minutes):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id="snap", authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
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

    def replaced_chain(self):
        self.decision("d1", 0)
        self.decision("d2", 5)
        self.freshness("d1", 6, action=REVALIDATION_REPLACED, replacement="d2")
        self.pointer("d1")
        return self.results.record(TASK_ID, self.reconciler.reconcile(TASK_ID))

    def tampered(self, record, **changes):
        return self.result_store.save(replace(record, result_id=f"tampered-{len(changes)}-{id(changes)}", **changes))


def _mentions(items, text):
    return any(text in item for item in items)


def test_valid_result_verifies():
    f = _Fixture()
    record = f.replaced_chain()

    result = f.verifier.verify(TASK_ID, record.result_id)

    assert record.status == RECONCILIATION_COMPLETED
    assert result.status == RECONCILIATION_VERIFICATION_VALID and result.valid and not result.invalid
    assert result.mismatches == () and result.missing_evidence == ()


def test_recorded_invalid_chain_that_is_still_invalid_verifies():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)  # never linked -- chain stays invalid
    record = f.results.record(TASK_ID, f.reconciler.reconcile(TASK_ID))

    assert f.verifier.verify(TASK_ID, record.result_id).valid


def test_missing_decisions_are_missing_evidence():
    f = _Fixture()
    record = f.tampered(f.replaced_chain(), current_decision_id="gone", authoritative_decision_id="gone")

    result = f.verifier.verify(TASK_ID, record.result_id)

    assert result.status == RECONCILIATION_VERIFICATION_INVALID
    assert _mentions(result.missing_evidence, "current decision gone no longer exists")
    assert _mentions(result.missing_evidence, "authoritative decision gone no longer exists")


def test_mismatched_authoritative_decision_is_reported():
    f = _Fixture()
    record = f.replaced_chain()
    stale = f.tampered(record, authoritative_decision_id="d1", current_decision_id="d1", changed=False, changes=())

    result = f.verifier.verify(TASK_ID, stale.result_id)

    assert result.invalid
    assert _mentions(result.mismatches, "does not match the validated chain's authoritative decision d2")


def test_chain_advanced_since_recording_is_a_mismatch():
    f = _Fixture()
    record = f.replaced_chain()
    f.decision("d3", 10)
    f.freshness("d2", 11, action=REVALIDATION_REPLACED, replacement="d3")

    result = f.verifier.verify(TASK_ID, record.result_id)

    assert _mentions(result.mismatches, "does not match the validated chain's authoritative decision d3")


def test_incorrect_state_change_flag_is_reported():
    f = _Fixture()
    record = f.replaced_chain()
    wrong = f.tampered(record, changed=False)

    result = f.verifier.verify(TASK_ID, wrong.result_id)

    assert _mentions(result.mismatches, "state-change flag disagrees with the recorded changes")
    assert _mentions(result.mismatches, "recorded as unchanged, but the current decision moved from d1 to d2")


def test_missing_authoritative_evidence_fails_closed():
    f = _Fixture()
    record = f.replaced_chain()
    f.freshness("d2", 7, status="unknown")  # chain can no longer be validated

    result = f.verifier.verify(TASK_ID, record.result_id)

    assert result.invalid
    assert _mentions(result.missing_evidence, "can no longer establish an authoritative decision to confirm d2")
    assert _mentions(result.mismatches, "recorded chain validity (True) no longer matches")


def test_unknown_result_is_missing_evidence():
    f = _Fixture()
    record = f.replaced_chain()

    assert f.verifier.verify(TASK_ID, "nope").missing_evidence == (
        "reconciliation result nope does not exist for task task-1",
    )
    assert f.verifier.verify("task-2", record.result_id).invalid


def test_unsupported_schema_version_is_reported():
    f = _Fixture()
    old = f.tampered(f.replaced_chain(), schema_version=0)

    result = f.verifier.verify(TASK_ID, old.result_id)

    assert _mentions(result.mismatches, "unsupported schema version 0 (expected 1)")


def test_status_and_conflicts_must_match_the_record():
    f = _Fixture()
    record = f.replaced_chain()
    forged = f.tampered(record, conflicts=("current pointer elsewhere conflicts",))

    result = f.verifier.verify(TASK_ID, forged.result_id)

    assert _mentions(result.mismatches, "recorded status 'completed' contradicts")
    assert _mentions(result.mismatches, "conflict is missing from the unresolved issues")
    assert _mentions(result.mismatches, "does not concern the current pointer")


def test_integrity_failures_invalidate_the_result():
    integrity = SimpleNamespace(
        check=lambda task_id, decision_id: SimpleNamespace(status=INTEGRITY_INVALID, issues=("tampered",))
    )
    f = _Fixture(integrity_service=integrity)
    record = f.replaced_chain()

    result = f.verifier.verify(TASK_ID, record.result_id)

    assert _mentions(result.mismatches, "authoritative decision d2 failed its integrity check: tampered")


def test_repeated_verification_is_deterministic_and_read_only():
    f = _Fixture()
    record = f.tampered(f.replaced_chain(), changed=False)
    before = (
        f.decision_store.history(TASK_ID), f.freshness_store.list_for_task(TASK_ID),
        f.index_store.get(TASK_ID), f.results.history(TASK_ID),
    )

    first = f.verifier.verify(TASK_ID, record.result_id)
    second = f.verifier.verify(TASK_ID, record.result_id)

    assert first == second
    assert before == (
        f.decision_store.history(TASK_ID), f.freshness_store.list_for_task(TASK_ID),
        f.index_store.get(TASK_ID), f.results.history(TASK_ID),
    )


@pytest.mark.parametrize("args", [("", "r"), ("t", ""), (None, "r")])
def test_invalid_arguments_are_rejected(args):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationError):
        LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService().verify(*args)
