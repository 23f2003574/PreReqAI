from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_STALE,
    REVALIDATION_REPLACED,
    SUPERSESSION_LIFECYCLE_BLOCKED,
    SUPERSESSION_LIFECYCLE_CLEAN,
    SUPERSESSION_LIFECYCLE_EXECUTION_FAILED,
    SUPERSESSION_LIFECYCLE_RESOLVED,
    SUPERSESSION_LIFECYCLE_UNSAFE,
    SUPERSESSION_LIFECYCLE_VALIDATION_FAILED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultError,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _FakeRevalidation:
    def __init__(self, fail_for=()):
        self.calls, self.fail_for = [], set(fail_for)

    def revalidate(self, task_id, decision_id):
        self.calls.append(decision_id)
        if decision_id in self.fail_for:
            raise RuntimeError("snapshot service unavailable")
        return SimpleNamespace(action="reused", new_decision_id=None)


class _Fixture:
    def __init__(self, revalidation=None, **overrides):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.audit_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditStore()
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            decision_store=self.decision_store, store=self.supersession_store,
            freshness_audit_service=audit_service, chain_index_store=self.index_store,
        )
        self.revalidation = revalidation or _FakeRevalidation()
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService(
            decision_store=self.decision_store, supersession_store=self.supersession_store,
            freshness_audit_service=audit_service, chain_index_store=self.index_store,
            revalidation_service=self.revalidation,
            audit_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService(
                store=self.audit_store
            ),
            **overrides,
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
                reason="r", recorded_at=T0, supersession_id=f"s-{old}-{new}",
            )
        )

    def stale_pointer(self, first=EXECUTION_DECISION_ALLOW, second=EXECUTION_DECISION_ALLOW):
        self.decision("d1", 0, verdict=first)
        self.decision("d2", 5, verdict=second)
        self.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=self.index_store.get(TASK_ID).links, current_decision_id="d1", updated_at=T0,
            )
        )

    def disagreement(self, prefix="d", start=0):
        a, b, c = (f"{prefix}{i}" for i in (1, 2, 3))
        for offset, decision_id in enumerate((a, b, c)):
            self.decision(decision_id, start + offset * 5)
        self.raw(a, c)
        self.freshness_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=a, freshness_status=FRESHNESS_STALE, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=True,
                revalidation_action=REVALIDATION_REPLACED, replacement_decision_id=b, recorded_at=_at(start + 11),
                audit_id=f"a-{a}",
            )
        )


def test_successful_lifecycle_is_persisted_with_exact_references():
    f = _Fixture()
    f.stale_pointer()
    lifecycle = f.service.resolve(TASK_ID)
    results = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService()

    record = results.record(TASK_ID, lifecycle)

    assert record.state == SUPERSESSION_LIFECYCLE_RESOLVED
    assert (record.lifecycle_id, record.operation_id, record.audit_id) == (
        lifecycle.lifecycle_id, lifecycle.operation_id, lifecycle.audit_id,
    )
    assert record.conflicts == lifecycle.conflicts and record.planned_actions == lifecycle.planned_actions
    assert record.applied == lifecycle.applied and record.terminal_decision_id == "d2"
    assert record.verification == lifecycle.verification and record.verification_status == "valid"
    assert record.completed_at == lifecycle.completed_at and record.schema_version == 1
    assert record.to_dict()["recorded_at"] == record.recorded_at.isoformat()


def test_partial_resolution_is_persisted():
    f = _Fixture(revalidation=_FakeRevalidation(fail_for={"e1"}))
    f.disagreement("d", 0)
    f.disagreement("e", 100)
    lifecycle = f.service.resolve(TASK_ID)

    record = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService().record(TASK_ID, lifecycle)

    assert record.state == SUPERSESSION_LIFECYCLE_BLOCKED and record.partial is True
    assert record.failed == lifecycle.failed and "snapshot service unavailable" in record.failed[0].detail
    assert record.remaining_blockers == lifecycle.remaining_blockers


def test_blocked_lifecycle_is_persisted():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")

    record = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService().record(
        TASK_ID, f.service.resolve(TASK_ID)
    )

    assert record.state == SUPERSESSION_LIFECYCLE_BLOCKED and record.partial is False
    assert record.skipped and record.applied == ()


def test_failed_verification_is_persisted_as_unsafe():
    failing = SimpleNamespace(
        verify=lambda task_id, operation_id: SimpleNamespace(
            status="invalid", mismatches=("audit disagrees",), blocking_issues=(), terminal_decision_id=None,
        )
    )
    f = _Fixture(verification_service=failing)
    f.stale_pointer()

    record = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService().record(
        TASK_ID, f.service.resolve(TASK_ID)
    )

    assert record.state == SUPERSESSION_LIFECYCLE_UNSAFE
    assert record.verification_status == "invalid" and "audit disagrees" in record.remaining_blockers


def test_duplicate_recording_is_idempotent_and_latest_history_work():
    f = _Fixture()
    f.stale_pointer()
    results = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService()
    assert results.latest(TASK_ID) is None and results.history(TASK_ID) == []

    first_run = f.service.resolve(TASK_ID)
    first = results.record(TASK_ID, first_run)
    again = results.record(TASK_ID, first_run)
    second = results.record(TASK_ID, f.service.resolve(TASK_ID))  # clean re-run

    assert again == first
    assert second.state == SUPERSESSION_LIFECYCLE_CLEAN and second.operation_id is None
    assert [r.result_id for r in results.history(TASK_ID)] == [first.result_id, second.result_id]
    assert results.latest(TASK_ID) == second
    assert results.get(TASK_ID, first.result_id) == first
    assert results.get("task-2", first.result_id) is None and results.get(TASK_ID, "missing") is None


def test_history_is_immutable_and_reads_are_side_effect_free():
    f = _Fixture()
    f.stale_pointer()
    results = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService()
    record = results.record(TASK_ID, f.service.resolve(TASK_ID))

    with pytest.raises(Exception):
        record.state = SUPERSESSION_LIFECYCLE_CLEAN
    snapshot = results.history(TASK_ID)
    snapshot.clear()
    assert results.history(TASK_ID) == [record]
    assert results.get(TASK_ID, record.result_id) is not record


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    f.decision("d1", 0)
    lifecycle = f.service.resolve(TASK_ID)
    results = LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService()

    for call in (
        lambda: results.record("task-2", lifecycle),
        lambda: results.record(TASK_ID, None),
        lambda: results.history(""),
        lambda: results.get(TASK_ID, ""),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultError):
            call()
