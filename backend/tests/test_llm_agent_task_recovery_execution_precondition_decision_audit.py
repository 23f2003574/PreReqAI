from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW, blocking_conditions=(), warnings=(), task_id=TASK_ID):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=task_id, snapshot_id="snap-1", authorization_id="auth-1", decision=decision,
        reason="test reason", blocking_conditions=blocking_conditions, warnings=warnings,
        validation_result=None, drift_classification=None, approval_reconciliation=None, created_at=created_at,
    )


def _stack():
    decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    audit_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService(decision_store=decision_store)
    return decision_store, audit_service


def test_record_creates_an_audit_entry():
    decision_store, audit_service = _stack()
    decision = decision_store.save(_decision(blocking_conditions=("dependency unresolved",), warnings=("w1",)))

    record = audit_service.record(TASK_ID, decision.decision_id, actor="alice", operation_id="op-1")

    assert record.task_id == TASK_ID
    assert record.decision_id == decision.decision_id
    assert record.decision == EXECUTION_DECISION_ALLOW
    assert record.snapshot_id == decision.snapshot_id
    assert record.authorization_id == decision.authorization_id
    assert record.reason == decision.reason
    assert record.blocking_conditions == ("dependency unresolved",)
    assert record.warnings == ("w1",)
    assert record.actor == "alice"
    assert record.operation_id == "op-1"


def test_get_retrieves_a_recorded_audit_entry():
    decision_store, audit_service = _stack()
    decision = decision_store.save(_decision())
    record = audit_service.record(TASK_ID, decision.decision_id)

    fetched = audit_service.get(record.audit_id)

    assert fetched == record


def test_get_missing_audit_returns_none():
    _, audit_service = _stack()
    assert audit_service.get("never-existed") is None


def test_list_returns_chronological_task_history():
    decision_store, audit_service = _stack()
    d1 = decision_store.save(_decision(created_at=NOW))
    d2 = decision_store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=1)))

    r1 = audit_service.record(TASK_ID, d1.decision_id)
    r2 = audit_service.record(TASK_ID, d2.decision_id)

    history = audit_service.list(TASK_ID)
    assert [r.audit_id for r in history] == [r1.audit_id, r2.audit_id]


def test_multiple_decisions_produce_independent_audit_records():
    decision_store, audit_service = _stack()
    d1 = decision_store.save(_decision(created_at=NOW))
    d2 = decision_store.save(_decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW + timedelta(seconds=1)))

    r1 = audit_service.record(TASK_ID, d1.decision_id)
    r2 = audit_service.record(TASK_ID, d2.decision_id)

    assert r1.audit_id != r2.audit_id
    assert r1.decision_id != r2.decision_id
    assert len(audit_service.list(TASK_ID)) == 2


def test_recording_does_not_modify_the_decision():
    decision_store, audit_service = _stack()
    decision = decision_store.save(_decision())

    audit_service.record(TASK_ID, decision.decision_id, actor="alice")

    unchanged = decision_store.get(decision.decision_id)
    assert unchanged == decision


def test_append_only_repeated_recording_creates_new_entries():
    decision_store, audit_service = _stack()
    decision = decision_store.save(_decision())

    first = audit_service.record(TASK_ID, decision.decision_id)
    second = audit_service.record(TASK_ID, decision.decision_id)

    assert first.audit_id != second.audit_id
    assert audit_service.get(first.audit_id) == first
    assert len(audit_service.list(TASK_ID)) == 2


def test_missing_decision_raises():
    _, audit_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError):
        audit_service.record(TASK_ID, "never-existed")


def test_decision_from_a_different_task_is_rejected():
    decision_store, audit_service = _stack()
    decision = decision_store.save(_decision(task_id="task-2"))

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError):
        audit_service.record(TASK_ID, decision.decision_id)


def test_actor_and_operation_id_default_to_none():
    decision_store, audit_service = _stack()
    decision = decision_store.save(_decision())

    record = audit_service.record(TASK_ID, decision.decision_id)

    assert record.actor is None
    assert record.operation_id is None


def test_record_rejects_blank_arguments():
    _, audit_service = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError):
        audit_service.record("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditError):
        audit_service.record(TASK_ID, "")


def test_deterministic_ordering_regardless_of_save_order():
    decision_store, audit_service = _stack()
    d1 = decision_store.save(_decision(created_at=NOW))
    d2 = decision_store.save(_decision(created_at=NOW + timedelta(seconds=1)))
    d3 = decision_store.save(_decision(created_at=NOW + timedelta(seconds=2)))

    r3 = audit_service.record(TASK_ID, d3.decision_id)
    r1 = audit_service.record(TASK_ID, d1.decision_id)
    r2 = audit_service.record(TASK_ID, d2.decision_id)

    history = audit_service.list(TASK_ID)
    assert [r.audit_id for r in history] == [r3.audit_id, r1.audit_id, r2.audit_id]
