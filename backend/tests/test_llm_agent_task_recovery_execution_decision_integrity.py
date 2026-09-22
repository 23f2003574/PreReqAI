import dataclasses
from datetime import datetime, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    AgentTaskRecoveryExecutionPreconditionDecision,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore,
    InvalidAgentTaskRecoveryExecutionDecisionIntegrityError,
    LLMAgentTaskRecoveryExecutionDecisionIntegrityService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
)
from backend.agent_task_recovery_guardrails import (
    ACTIVE,
    AgentTaskRecoveryPreflightAuthorization,
    InMemoryAgentTaskRecoveryPreflightAuthorizationStore,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _snapshot(snapshot_id="snap-1"):
    return AgentTaskRecoveryExecutionPreconditionSnapshot(
        task_id=TASK_ID, authorization_id="auth-1", preflight_id="preflight-1", approval_id="approval-1",
        authorization_status=ACTIVE, task_state=None, recovery_plan=None, retry_eligibility=None,
        readiness=None, captured_at=NOW, snapshot_id=snapshot_id,
    )


def _authorization(authorization_id="auth-1"):
    return AgentTaskRecoveryPreflightAuthorization(
        task_id=TASK_ID, preflight_id="preflight-1", approval_id="approval-1", status=ACTIVE,
        revocation_reason=None, created_at=NOW, revoked_at=None, authorization_id=authorization_id,
    )


def _decision(decision=EXECUTION_DECISION_ALLOW, snapshot_id="snap-1", authorization_id="auth-1"):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=TASK_ID, snapshot_id=snapshot_id, authorization_id=authorization_id, decision=decision,
        reason="test reason", blocking_conditions=(), warnings=(), validation_result=None,
        drift_classification=None, approval_reconciliation=None, created_at=NOW,
    )


def _stack():
    decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    snapshot_store = InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore()
    snapshot_service = LLMAgentTaskRecoveryExecutionPreconditionSnapshotService(store=snapshot_store)
    authorization_store = InMemoryAgentTaskRecoveryPreflightAuthorizationStore()
    authorization_service = LLMAgentTaskRecoveryPreflightAuthorizationService(store=authorization_store)
    audit_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService(decision_store=decision_store)
    integrity_service = LLMAgentTaskRecoveryExecutionDecisionIntegrityService(
        decision_store=decision_store, snapshot_service=snapshot_service,
        authorization_service=authorization_service, audit_service=audit_service,
    )
    return {
        "decision_store": decision_store, "snapshot_store": snapshot_store, "snapshot_service": snapshot_service,
        "authorization_store": authorization_store, "authorization_service": authorization_service,
        "audit_service": audit_service, "integrity_service": integrity_service,
    }


def test_valid_decision_passes_integrity_check():
    s = _stack()
    s["snapshot_store"].save(_snapshot())
    s["authorization_store"].save(_authorization())
    decision = s["decision_store"].save(_decision())

    result = s["integrity_service"].check(TASK_ID, decision.decision_id)

    assert result.status == INTEGRITY_VALID
    assert result.issues == ()


def test_missing_snapshot_reference_is_invalid():
    s = _stack()
    s["authorization_store"].save(_authorization())
    decision = s["decision_store"].save(_decision(snapshot_id="ghost-snapshot"))

    result = s["integrity_service"].check(TASK_ID, decision.decision_id)

    assert result.status == INTEGRITY_INVALID
    assert any("snapshot" in issue for issue in result.issues)


def test_missing_authorization_reference_is_invalid():
    s = _stack()
    s["snapshot_store"].save(_snapshot())
    decision = s["decision_store"].save(_decision(authorization_id="ghost-auth"))

    result = s["integrity_service"].check(TASK_ID, decision.decision_id)

    assert result.status == INTEGRITY_INVALID
    assert any("authorization" in issue for issue in result.issues)


def test_malformed_evidence_is_invalid():
    s = _stack()
    s["snapshot_store"].save(_snapshot())
    s["authorization_store"].save(_authorization())
    decision = s["decision_store"].save(_decision())
    tampered = dataclasses.replace(decision, blocking_conditions=["not", "a", "tuple"])
    s["decision_store"]._store._by_id[tampered.decision_id] = tampered

    result = s["integrity_service"].check(TASK_ID, tampered.decision_id)

    assert result.status == INTEGRITY_INVALID
    assert any("blocking_conditions" in issue for issue in result.issues)


def test_task_mismatch_is_invalid():
    s = _stack()
    decision = s["decision_store"].save(_decision())

    result = s["integrity_service"].check("a-different-task", decision.decision_id)

    assert result.status == INTEGRITY_INVALID
    assert any("no decision" in issue for issue in result.issues)


def test_unsupported_decision_state_is_invalid():
    s = _stack()
    s["snapshot_store"].save(_snapshot())
    s["authorization_store"].save(_authorization())
    decision = s["decision_store"].save(_decision())
    tampered = dataclasses.replace(decision, decision="unknown_state")
    s["decision_store"]._store._by_id[tampered.decision_id] = tampered

    result = s["integrity_service"].check(TASK_ID, tampered.decision_id)

    assert result.status == INTEGRITY_INVALID
    assert any("not a supported value" in issue for issue in result.issues)


def test_missing_decision_id_is_invalid():
    s = _stack()
    result = s["integrity_service"].check(TASK_ID, "never-existed")

    assert result.status == INTEGRITY_INVALID


def test_check_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionIntegrityError):
        s["integrity_service"].check("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionIntegrityError):
        s["integrity_service"].check(TASK_ID, "")


def test_repeated_checks_are_deterministic():
    s = _stack()
    s["snapshot_store"].save(_snapshot())
    s["authorization_store"].save(_authorization())
    decision = s["decision_store"].save(_decision())

    first = s["integrity_service"].check(TASK_ID, decision.decision_id)
    second = s["integrity_service"].check(TASK_ID, decision.decision_id)

    assert first.status == second.status == INTEGRITY_VALID
    assert first.issues == second.issues == ()


def test_inconsistent_audit_evidence_is_invalid():
    s = _stack()
    s["snapshot_store"].save(_snapshot())
    s["authorization_store"].save(_authorization())
    decision = s["decision_store"].save(_decision())
    record = s["audit_service"].record(TASK_ID, decision.decision_id)
    tampered_audit = dataclasses.replace(record, snapshot_id="tampered-snapshot")
    s["audit_service"]._store._by_id[tampered_audit.audit_id] = tampered_audit
    s["audit_service"]._store._by_task[TASK_ID] = [tampered_audit]

    result = s["integrity_service"].check(TASK_ID, decision.decision_id)

    assert result.status == INTEGRITY_INVALID
    assert any("audit record" in issue for issue in result.issues)
