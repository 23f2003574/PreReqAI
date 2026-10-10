from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_DELEGATED,
    CONFLICT_ACTION_FAILED,
    CONFLICT_ACTION_SKIPPED,
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    FRESHNESS_STALE,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_REVALIDATION,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _FakeRevalidation:
    def __init__(self, fail_for=()):
        self.calls = []
        self.fail_for = set(fail_for)

    def revalidate(self, task_id, decision_id):
        self.calls.append(decision_id)
        if decision_id in self.fail_for:
            raise RuntimeError("snapshot service unavailable")
        return SimpleNamespace(action="reused", new_decision_id=None)


class _Fixture:
    def __init__(self, revalidation=None):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(store=self.freshness_store)
        common = dict(
            decision_store=self.decision_store, chain_index_store=self.index_store,
            freshness_audit_service=audit_service,
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        resolution = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=self.supersession_store, **common
        )
        detector = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
            supersession_store=self.supersession_store, resolution_service=resolution, **common
        )
        self.planner = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService(
            conflict_service=detector, resolution_service=resolution,
        )
        self.revalidation = revalidation or _FakeRevalidation()
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService(
            plan_service=self.planner,
            plan_validation_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService(
                plan_service=self.planner, decision_store=self.decision_store,
                supersession_store=self.supersession_store, freshness_audit_service=audit_service,
            ),
            reconciliation_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common),
            revalidation_service=self.revalidation,
            supersession_validation_service=LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
                supersession_store=self.supersession_store, **common
            ),
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

    def raw(self, old, new, reason="r"):
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=EXECUTION_DECISION_ALLOW, replacement_decision=EXECUTION_DECISION_ALLOW,
                reason=reason, recorded_at=T0, supersession_id=f"s-{old}-{new}",
            )
        )

    def audit_link(self, old, new, minutes):
        self.freshness_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
                task_id=TASK_ID, decision_id=old, freshness_status=FRESHNESS_STALE, freshness_reason="r",
                decision_state_version="v1", current_state_version="v2", revalidated=True,
                revalidation_action=REVALIDATION_REPLACED, replacement_decision_id=new, recorded_at=_at(minutes),
                audit_id=f"a-{old}",
            )
        )

    def stale_pointer(self):
        self.decision("d1", 0, verdict=EXECUTION_DECISION_REVIEW)
        self.decision("d2", 5, verdict=EXECUTION_DECISION_BLOCK)
        self.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=self.index_store.get(TASK_ID).links, current_decision_id="d1", updated_at=T0,
            )
        )
        return self.planner.plan(TASK_ID)

    def disagreement(self, prefix="d", start=0):
        a, b, c = (f"{prefix}{i}" for i in (1, 2, 3))
        for offset, decision_id in enumerate((a, b, c)):
            self.decision(decision_id, start + offset * 5)
        self.raw(a, c)
        self.audit_link(a, b, start + 11)


def test_repairable_pointer_is_applied_without_changing_decisions():
    f = _Fixture()
    plan = f.stale_pointer()
    before = f.decision_store.history(TASK_ID)

    result = f.service.execute(TASK_ID, plan)

    assert result.plan_valid and plan.items[0].classification == PLAN_REPAIRABLE_METADATA
    (applied,) = result.applied
    assert applied.outcome == CONFLICT_ACTION_APPLIED and "d1 -> d2" in applied.detail
    assert f.index_store.get(TASK_ID).current_decision_id == "d2"
    assert f.decision_store.history(TASK_ID) == before
    assert f.decision_store.get("d2").decision == EXECUTION_DECISION_BLOCK
    assert result.still_blocking == ()
    assert len(result.batch_validations) == 1 and result.final_validation.valid


def test_revalidation_is_delegated_and_conflict_stays_blocking():
    f = _Fixture()
    f.disagreement()
    plan = f.planner.plan(TASK_ID)

    result = f.service.execute(TASK_ID, plan)

    delegated = [o for o in result.applied if o.classification == PLAN_REQUIRES_REVALIDATION]
    assert delegated and delegated[0].outcome == CONFLICT_ACTION_DELEGATED
    assert f.revalidation.calls == ["d1"]
    assert any(cid.startswith("freshness_disagreement:") for cid in result.still_blocking)
    assert result.final_validation.invalid


def test_manual_review_conflicts_are_left_untouched():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")
    records = f.supersession_store.list_for_task(TASK_ID)

    result = f.service.execute(TASK_ID, f.planner.plan(TASK_ID))

    assert result.applied == () and result.failed == ()
    assert [o.outcome for o in result.skipped] == [CONFLICT_ACTION_SKIPPED]
    assert result.still_blocking == tuple(i.conflict_id for i in f.planner.plan(TASK_ID).items)
    assert result.batch_validations == ()
    assert f.supersession_store.list_for_task(TASK_ID) == records


def test_stale_plan_items_are_not_executed():
    f = _Fixture()
    plan = f.stale_pointer()
    f.index_store.save(replace(f.index_store.get(TASK_ID), current_decision_id="d2"))  # resolved elsewhere

    result = f.service.execute(TASK_ID, plan)

    assert not result.plan_valid
    assert result.applied == () and result.skipped[0].detail == "not validated against current evidence"


def test_partial_failure_keeps_successful_work_and_reports_the_rest():
    f = _Fixture(revalidation=_FakeRevalidation(fail_for={"e1"}))
    f.disagreement("d", 0)
    f.disagreement("e", 100)

    result = f.service.execute(TASK_ID, f.planner.plan(TASK_ID))

    assert [o.outcome for o in result.applied] == [CONFLICT_ACTION_DELEGATED]
    (failure,) = result.failed
    assert failure.outcome == CONFLICT_ACTION_FAILED and "snapshot service unavailable" in failure.detail
    assert f.revalidation.calls == ["d1", "e1"]
    assert len(result.still_blocking) >= 2


def test_missing_revalidation_service_is_a_reported_failure():
    f = _Fixture()
    f.service._revalidation_service = None
    f.disagreement()

    result = f.service.execute(TASK_ID, f.planner.plan(TASK_ID))

    assert result.failed and "no freshness revalidation service" in result.failed[0].detail


def test_repeated_execution_is_idempotent():
    f = _Fixture()
    plan = f.stale_pointer()

    first = f.service.execute(TASK_ID, plan)
    index_after = f.index_store.get(TASK_ID)
    second = f.service.execute(TASK_ID, plan)

    assert len(first.applied) == 1
    assert second.applied == () and len(second.skipped) == 1
    assert f.index_store.get(TASK_ID) == index_after


def test_post_execution_chain_validation_is_reported():
    f = _Fixture()
    plan = f.stale_pointer()

    result = f.service.execute(TASK_ID, plan)

    assert result.final_validation.terminal_decision_id == "d2"
    assert result.final_validation is result.batch_validations[-1]


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError):
        f.service.execute("", f.planner.plan(TASK_ID))
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError):
        f.service.execute(TASK_ID, None)
