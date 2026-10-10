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
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleError,
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


def test_clean_state_runs_nothing():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_CLEAN
    assert result.terminal_decision_id == "d2" and result.remaining_blockers == ()
    assert result.operation_id is None and f.audit_store.list_for_task(TASK_ID) == []


def test_successful_resolution_is_audited_and_verified():
    f = _Fixture()
    f.stale_pointer()

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_RESOLVED, result.remaining_blockers
    assert len(result.conflicts) == len(result.planned_actions) == len(result.applied) == 1
    assert result.terminal_decision_id == "d2" and result.verification.valid
    assert result.audit_id == f.audit_store.list_for_task(TASK_ID)[0].audit_id
    assert result.operation_id == f.audit_store.list_for_task(TASK_ID)[0].operation_id


def test_block_terminal_is_never_promoted():
    f = _Fixture()
    f.stale_pointer(first=EXECUTION_DECISION_REVIEW, second=EXECUTION_DECISION_BLOCK)

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_BLOCKED and result.partial is True
    assert any("'block'" in blocker for blocker in result.remaining_blockers)
    assert f.decision_store.get("d2").decision == EXECUTION_DECISION_BLOCK


def test_partial_resolution_reports_remaining_blockers():
    f = _Fixture(revalidation=_FakeRevalidation(fail_for={"e1"}))
    f.disagreement("d", 0)
    f.disagreement("e", 100)

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_BLOCKED and result.partial is True
    assert len(result.applied) == 1 and len(result.failed) == 1
    assert result.terminal_decision_id is None and result.remaining_blockers


def test_manual_review_blockers_are_left_untouched():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")
    records = f.supersession_store.list_for_task(TASK_ID)

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_BLOCKED and result.partial is False
    assert result.applied == () and len(result.skipped) == 1
    assert f.supersession_store.list_for_task(TASK_ID) == records


def test_validation_failure_stops_before_execution():
    rejecting = SimpleNamespace(validate=lambda task_id, plan: SimpleNamespace(valid=False, issues=("stale plan",)))
    f = _Fixture(plan_validation_service=rejecting)
    f.stale_pointer()

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_VALIDATION_FAILED
    assert result.applied == () and result.operation_id is None
    assert f.index_store.get(TASK_ID).current_decision_id == "d1"
    assert result.remaining_blockers == ("stale plan",)


def test_execution_failure_is_reported():
    def explode(task_id, plan):
        raise RuntimeError("store offline")

    f = _Fixture(execution_service=SimpleNamespace(execute=explode))
    f.stale_pointer()

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_EXECUTION_FAILED
    assert "store offline" in result.errors[0]
    assert f.audit_store.list_for_task(TASK_ID) == []


def test_verification_failure_is_reported_unsafe():
    failing = SimpleNamespace(
        verify=lambda task_id, operation_id: SimpleNamespace(
            mismatches=("audit disagrees with state",), blocking_issues=(), terminal_decision_id=None,
        )
    )
    f = _Fixture(verification_service=failing)
    f.stale_pointer()

    result = f.service.resolve(TASK_ID)

    assert result.state == SUPERSESSION_LIFECYCLE_UNSAFE
    assert "audit disagrees with state" in result.remaining_blockers


def test_repeated_lifecycle_is_idempotent_once_resolved():
    f = _Fixture()
    f.stale_pointer()

    first = f.service.resolve(TASK_ID)
    second = f.service.resolve(TASK_ID)

    assert first.state == SUPERSESSION_LIFECYCLE_RESOLVED
    assert second.state == SUPERSESSION_LIFECYCLE_CLEAN and second.terminal_decision_id == "d2"
    assert len(f.audit_store.list_for_task(TASK_ID)) == 1
    assert [d.decision_id for d in f.decision_store.history(TASK_ID)] == ["d1", "d2"]


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService().resolve(task_id)
