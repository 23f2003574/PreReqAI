from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    PLAN_REPAIRABLE_METADATA,
    PLAN_VALIDATION_INVALID,
    PLAN_VALIDATION_VALID,
    AgentTaskRecoveryExecutionDecisionFreshnessChainIndex,
    AgentTaskRecoveryExecutionDecisionSupersessionRecord,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore,
    InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore,
    InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore,
    InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError,
    LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService,
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
        audit_service = LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService(
            store=InMemoryAgentTaskRecoveryExecutionDecisionFreshnessAuditStore()
        )
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
        self.service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService(
            plan_service=self.planner, decision_store=self.decision_store,
            supersession_store=self.supersession_store, freshness_audit_service=audit_service,
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

    def conflicted(self):
        for index, decision_id in enumerate(("d1", "d2", "d3")):
            self.decision(decision_id, index * 5)
        self.raw("d1", "d2")
        self.raw("d1", "d3", reason=" ")
        return self.planner.plan(TASK_ID)


def _mentions(result, text):
    return any(text in issue for issue in result.issues)


def test_current_plan_is_valid_and_all_conflicts_block():
    f = _Fixture()
    plan = f.conflicted()

    result = f.service.validate(TASK_ID, plan)

    assert result.status == PLAN_VALIDATION_VALID and result.valid and not result.invalid, result.issues
    assert result.validated_conflicts == tuple(item.conflict_id for item in plan.items)
    assert result.blocking_conflicts == result.validated_conflicts


def test_empty_plan_for_a_clean_chain_is_valid():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")

    result = f.service.validate(TASK_ID, f.planner.plan(TASK_ID))

    assert result.valid and result.validated_conflicts == () and result.blocking_conflicts == ()


def test_stale_plan_missing_a_new_conflict_is_invalid():
    f = _Fixture()
    plan = f.conflicted()
    f.raw("d2", "gone")

    result = f.service.validate(TASK_ID, plan)

    assert result.status == PLAN_VALIDATION_INVALID
    assert _mentions(result, "is missing from the plan")


def test_resolved_conflict_in_the_plan_is_invalid():
    f = _Fixture()
    f.decision("d1", 0)
    f.decision("d2", 5)
    f.supersession.supersede(TASK_ID, "d1", "d2", "revalidated")
    f.index_store.save(
        AgentTaskRecoveryExecutionDecisionFreshnessChainIndex(
            task_id=TASK_ID, links=f.index_store.get(TASK_ID).links, current_decision_id="d1", updated_at=T0,
        )
    )
    plan = f.planner.plan(TASK_ID)
    assert plan.items[0].classification == PLAN_REPAIRABLE_METADATA
    f.index_store.save(replace(f.index_store.get(TASK_ID), current_decision_id="d2"))  # resolved since

    result = f.service.validate(TASK_ID, plan)

    assert _mentions(result, "no longer exists (already resolved or stale plan)")
    assert _mentions(result, "the plan assumed lineage state 'conflict', but it is now 'resolved'")
    assert result.validated_conflicts == () and result.blocking_conflicts == ()


def test_altered_or_state_changing_actions_are_invalid():
    f = _Fixture()
    plan = f.conflicted()
    item = plan.items[0]
    tampered = replace(
        plan, items=(replace(item, classification=PLAN_REPAIRABLE_METADATA, proposed_action="pick d2"),)
        + plan.items[1:],
    )

    result = f.service.validate(TASK_ID, tampered)

    assert _mentions(result, "plans a metadata repair for a multiple_successors conflict")
    assert _mentions(result, "planned proposed_action does not match")
    assert _mentions(result, "planned classification does not match")
    assert item.conflict_id not in result.validated_conflicts


def test_missing_evidence_is_invalid():
    f = _Fixture()
    plan = f.conflicted()
    item = plan.items[0]
    tampered = replace(
        plan, items=(replace(item, evidence_ids=item.evidence_ids + ("s-forged",), evidence_required=()),)
        + plan.items[1:],
    )

    result = f.service.validate(TASK_ID, tampered)

    assert _mentions(result, "cites evidence s-forged, which is not persisted")
    assert _mentions(result, "names no required evidence")


def test_duplicate_and_conflicting_actions_are_invalid():
    f = _Fixture()
    plan = f.conflicted()
    item = plan.items[0]

    duplicated = f.service.validate(TASK_ID, replace(plan, items=plan.items + (item,)))
    conflicting = f.service.validate(
        TASK_ID, replace(plan, items=plan.items + (replace(item, proposed_action="other"),))
    )

    assert _mentions(duplicated, f"conflict {item.conflict_id} is planned more than once")
    assert _mentions(conflicting, "planned more than once with conflicting actions")


def test_blocking_conflicts_must_stay_blocking():
    f = _Fixture()
    plan = f.conflicted()
    unblocked = replace(
        plan, execution_blocked=False, items=tuple(replace(i, execution_blocked=False) for i in plan.items)
    )

    result = f.service.validate(TASK_ID, unblocked)

    assert _mentions(result, "requires_manual_review conflict")
    assert _mentions(result, "does not keep execution blocked")
    assert _mentions(result, "the plan unblocks execution")
    assert result.blocking_conflicts == tuple(i.conflict_id for i in plan.items)


def test_plan_for_another_task_and_repeat_validation():
    f = _Fixture()
    plan = f.conflicted()
    before = (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID))

    first = f.service.validate(TASK_ID, replace(plan, task_id="task-2"))
    second = f.service.validate(TASK_ID, replace(plan, task_id="task-2"))

    assert first == second and _mentions(first, "made for task 'task-2'")
    assert before == (f.decision_store.history(TASK_ID), f.supersession_store.list_for_task(TASK_ID))


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError):
        f.service.validate("", f.planner.plan(TASK_ID))
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError):
        f.service.validate(TASK_ID, None)
