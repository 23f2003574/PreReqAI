import dataclasses
from datetime import datetime, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _decision(decision=EXECUTION_DECISION_ALLOW, blocking_conditions=(), warnings=()):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=TASK_ID, snapshot_id="snap-1", authorization_id="auth-1", decision=decision,
        reason="test reason", blocking_conditions=blocking_conditions, warnings=warnings,
        validation_result=None, drift_classification=None, approval_reconciliation=None, created_at=NOW,
    )


def _stack():
    decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    audit_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService(decision_store=decision_store)
    verification_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService(
        audit_service=audit_service, decision_store=decision_store
    )
    return decision_store, audit_service, verification_service


def test_valid_audit_record_verifies():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision(blocking_conditions=("b1",), warnings=("w1",)))
    record = audit_service.record(TASK_ID, decision.decision_id)

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert result.valid is True
    assert result.decision_found is True
    assert result.mismatches == ()
    assert result.missing_fields == ()
    assert result.reason is None


def test_missing_decision_fails_closed():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)

    # Simulate the referenced decision no longer existing in the store.
    empty_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    verification_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService(
        audit_service=audit_service, decision_store=empty_store
    )

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert result.valid is False
    assert result.decision_found is False
    assert result.mismatches == ()
    assert "no longer exists" in result.reason


def test_snapshot_id_mismatch_is_detected():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)
    record = dataclasses.replace(record, snapshot_id="snap-tampered")
    audit_service._store._by_id[record.audit_id] = record  # simulate an altered audit entry

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert result.valid is False
    assert "snapshot_id" in result.mismatches


def test_authorization_id_mismatch_is_detected():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)
    record = dataclasses.replace(record, authorization_id="auth-tampered")
    audit_service._store._by_id[record.audit_id] = record

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert "authorization_id" in result.mismatches


def test_decision_state_mismatch_is_detected():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision(decision=EXECUTION_DECISION_ALLOW))
    record = audit_service.record(TASK_ID, decision.decision_id)
    record = dataclasses.replace(record, decision=EXECUTION_DECISION_BLOCK)
    audit_service._store._by_id[record.audit_id] = record

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert "decision" in result.mismatches


def test_reason_blockers_and_warnings_mismatch_is_detected():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision(blocking_conditions=("b1",), warnings=("w1",)))
    record = audit_service.record(TASK_ID, decision.decision_id)
    record = dataclasses.replace(
        record, reason="tampered reason", blocking_conditions=("tampered",), warnings=("tampered",)
    )
    audit_service._store._by_id[record.audit_id] = record

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert set(result.mismatches) >= {"reason", "blocking_conditions", "warnings"}


def test_missing_required_fields_are_reported():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)
    record = dataclasses.replace(record, reason="")
    audit_service._store._by_id[record.audit_id] = record

    result = verification_service.verify(TASK_ID, record.audit_id)

    assert result.valid is False
    assert "reason" in result.missing_fields


def test_missing_audit_record_raises():
    _, _, verification_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError):
        verification_service.verify(TASK_ID, "never-existed")


def test_verify_rejects_blank_arguments():
    _, _, verification_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError):
        verification_service.verify("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError):
        verification_service.verify(TASK_ID, "")


def test_repeated_verification_is_deterministic():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)

    first = verification_service.verify(TASK_ID, record.audit_id)
    second = verification_service.verify(TASK_ID, record.audit_id)

    assert first.valid == second.valid
    assert first.mismatches == second.mismatches
    assert first.missing_fields == second.missing_fields


def test_verification_never_mutates_audit_history():
    decision_store, audit_service, verification_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)

    verification_service.verify(TASK_ID, record.audit_id)

    unchanged = audit_service.get(record.audit_id)
    assert unchanged == record
    assert len(audit_service.list(TASK_ID)) == 1
