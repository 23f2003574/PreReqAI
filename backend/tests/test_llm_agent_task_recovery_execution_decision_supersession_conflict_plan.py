from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    CONFLICT_SEVERITY_CRITICAL,
    CONFLICT_SEVERITY_HIGH,
    CONFLICT_SEVERITY_NONE,
    EXECUTION_DECISION_ALLOW,
    POINTER_STATUS_AGREES,
    POINTER_STATUS_DISAGREES,
    POINTER_STATUS_UNSET,
    RESOLUTION_CONFLICT,
    RESOLUTION_REJECTED,
    RESOLUTION_RESOLVED,
    SUPERSESSION_CONFLICT_INVALID_REASON,
    SUPERSESSION_CONFLICT_MISSING_DECISION,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_MANUAL_REVIEW,
    PLAN_REQUIRES_REVALIDATION,
    PLAN_UNRESOLVABLE,
    FRESHNESS_STALE,
    REVALIDATION_REPLACED,
    AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


def _at(minutes):
    return T0 + timedelta(minutes=minutes)


class _Fixture:
    def __init__(self):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.supersession_store = InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        self.index_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        self.freshness_store = InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        common = dict(
            decision_store=self.decision_store, chain_index_store=self.index_store,
            freshness_audit_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
                store=self.freshness_store
            ),
        )
        self.supersession = LLMAgentTaskRecoveryExecutionDecisionSupersessionService(
            store=self.supersession_store, **common
        )
        self.reconciler = LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common)
        resolution = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=self.supersession_store, **common
        )
        self.detector = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
            supersession_store=self.supersession_store, resolution_service=resolution, **common
        )
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService(
            conflict_service=self.detector, resolution_service=resolution,
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

    def raw(self, old, new, reason="r"):
        self.supersession_store.save(
            AgentTaskRecoveryExecutionDecisionSupersessionRecord(
                task_id=TASK_ID, previous_decision_id=old, replacement_decision_id=new,
                previous_decision=EXECUTION_DECISION_ALLOW, replacement_decision=EXECUTION_DECISION_ALLOW,
                reason=reason, recorded_at=T0, supersession_id=f"s-{old}-{new}",
            )
        )


    def decision_for(self, decision_id, minutes, task_id):
        return self.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=task_id, snapshot_id="snap", authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=_at(minutes),
                decision_id=decision_id,
            )
        )

    def point_at(self, decision_id):
        index = self.index_store.get(TASK_ID)
        self.index_store.save(
            AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
                task_id=TASK_ID, links=index.links if index else (), current_decision_id=decision_id, updated_at=T0,
            )
        )


def _classes(plan):
    return [(item.conflict_type, item.classification) for item in plan.items]


def test_empty_task_plans_nothing_but_stays_blocked():
    plan = _Fixture().service.plan(TASK_ID)

    assert plan.items == ()
    assert plan.execution_blocked is True  # no authoritative lineage exists
    assert set(plan.counts_by_classification.values()) == {0}


def test_clean_chain_has_an_empty_unblocked_plan():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")

    plan = f.service.plan(TASK_ID)

    assert plan.items == () and plan.execution_blocked is False


def test_stale_pointer_on_the_lineage_is_repairable_metadata():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    f.point_at("d1")

    (item,) = f.service.plan(TASK_ID).items

    assert item.classification == PLAN_REPAIRABLE_METADATA
    assert "ChainReconciliationService.reconcile()" in item.proposed_action
    assert item.depends_on == ("freshness_reconciliation",)
    assert item.execution_blocked is True
    assert f.index_store.get(TASK_ID).current_decision_id == "d1"  # planned, not applied


def test_freshness_disagreement_requires_revalidation():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d3")
    f.freshness_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessAuditRecord(
            task_id=TASK_ID, decision_id="d1", freshness_status=FRESHNESS_STALE, freshness_reason="r",
            decision_state_version="v1", current_state_version="v2", revalidated=True,
            revalidation_action=REVALIDATION_REPLACED, replacement_decision_id="d2", recorded_at=_at(11),
            audit_id="a-1",
        )
    )

    plan = f.service.plan(TASK_ID)

    (item,) = [i for i in plan.items if i.classification == PLAN_REQUIRES_REVALIDATION]
    assert item.evidence_ids == ("a-1", "s-d1-d3")
    assert item.depends_on == ("freshness_revalidation", "freshness_reconciliation")


def test_ambiguous_successors_require_manual_review_without_a_winner():
    f = _Fixture()
    for index, decision_id in enumerate(("d1", "d2", "d3")):
        f.decision(decision_id, index * 5)
    f.raw("d1", "d2")
    f.raw("d1", "d3")

    plan = f.service.plan(TASK_ID)

    (item,) = plan.items
    assert item.classification == PLAN_REQUIRES_MANUAL_REVIEW
    assert item.decision_ids == ("d1", "d2", "d3")
    assert "no successor is selected" in item.proposed_action
    assert plan.execution_blocked is True


def test_off_lineage_pointer_requires_manual_review():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision_for("foreign", 1, task_id="task-2")
    f.point_at("foreign")

    plan = f.service.plan(TASK_ID)

    assert _classes(plan) == [("pointer_disagreement", PLAN_REQUIRES_MANUAL_REVIEW)]
    assert "outside the validated lineage" in plan.items[0].proposed_action
    assert plan.execution_blocked is True


def test_missing_decision_and_cycle_are_unresolvable():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d2", "d1")
    f.raw("d2", "gone")

    plan = f.service.plan(TASK_ID)

    assert ("cycle", PLAN_UNRESOLVABLE) in _classes(plan)
    assert ("missing_decision", PLAN_UNRESOLVABLE) in _classes(plan)
    assert plan.counts_by_classification[PLAN_UNRESOLVABLE] >= 2


def test_mixed_conflicts_follow_detector_order_with_stable_ids():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.decision("d3", 6)
    f.raw("d1", "d2")
    f.raw("d1", "d3", reason=" ")
    f.raw("d1", "gone")

    first = f.service.plan(TASK_ID)
    second = f.service.plan(TASK_ID)

    assert first == second
    assert _classes(first) == [
        ("multiple_successors", PLAN_REQUIRES_MANUAL_REVIEW),
        ("missing_decision", PLAN_UNRESOLVABLE),
        ("invalid_reason", PLAN_REQUIRES_MANUAL_REVIEW),
    ]
    assert len({item.conflict_id for item in first.items}) == 3
    assert first.items[0].conflict_id.startswith("multiple_successors:")


def test_planning_is_read_only():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.raw("d1", "d2")
    f.raw("d2", "d1")
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID))

    f.service.plan(TASK_ID)

    assert before == (
        f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID), f.index_store.get(TASK_ID),
    )


@pytest.mark.parametrize("task_id", ["", None])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanError):
        LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService().plan(task_id)
