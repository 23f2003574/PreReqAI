from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    IMPACT_PLAN_VALIDATION_INVALID,
    IMPACT_PLAN_VALIDATION_VALID,
    INVALIDATION_INVALIDATE,
    INVALIDATION_MANUAL_REVIEW,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionPreconditionDecision,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError,
    LLMAgentTaskRecoveryExecutionDecisionChangeImpactService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"


class _Snapshots:
    def __init__(self):
        self.by_id = {}

    def add(self, snapshot_id, **overrides):
        fields = dict(
            task_id=TASK_ID, authorization_id="auth-1", preflight_id="pre-1", approval_id="appr-1",
            authorization_status="active", task_state="failed", recovery_plan="plan-a",
            retry_eligibility="eligible", readiness="ready", captured_at=T0, snapshot_id=snapshot_id,
        )
        fields.update(overrides)
        self.by_id[snapshot_id] = AgentTaskRecoveryExecutionPreconditionSnapshot(**fields)

    def get(self, task_id, snapshot_id):
        snapshot = self.by_id.get(snapshot_id)
        return snapshot if snapshot is not None and snapshot.task_id == task_id else None


class _Fixture:
    def __init__(self, resolution=None):
        self.decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self.snapshots = _Snapshots()
        self.pointer = SimpleNamespace(current_decision_id="d1")
        self.impact = LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(
            decision_store=self.decision_store, snapshot_service=self.snapshots,
        )
        self.staleness = LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService(
            chain_index_store=SimpleNamespace(get=lambda task_id: self.pointer),
        )
        self.planner = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService()
        self.service = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService(
            impact_service=self.impact, staleness_service=self.staleness, plan_service=self.planner,
            supersession_resolution_service=resolution,
        )
        self.snapshots.add("snap-1")
        self.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b")
        for index, (decision_id, verdict, snapshot_id) in enumerate(
            (("d1", EXECUTION_DECISION_ALLOW, "snap-1"), ("d2", EXECUTION_DECISION_BLOCK, "snap-2"))
        ):
            self.decision_store.save(
                AgentTaskRecoveryExecutionPreconditionDecision(
                    task_id=TASK_ID, snapshot_id=snapshot_id, authorization_id="auth-1", decision=verdict,
                    reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                    drift_classification=None, approval_reconciliation=None,
                    created_at=T0 + timedelta(minutes=index * 5), decision_id=decision_id,
                )
            )

    def make_plan(self):
        impact = self.impact.analyze(TASK_ID, "d1", "d2")
        return self.planner.plan(TASK_ID, self.staleness.check(TASK_ID, impact))


def _mentions(result, text):
    return any(text in issue for issue in result.issues)


def test_current_plan_is_valid():
    f = _Fixture()
    plan = f.make_plan()

    result = f.service.validate(TASK_ID, plan)

    assert result.status == IMPACT_PLAN_VALIDATION_VALID and result.valid, result.issues
    assert result.validated_actions == tuple(i.artifact_id for i in plan.items)
    assert "execution_pointer:d1" in result.blocking_actions


def test_stale_plan_missing_a_new_artifact_is_invalid():
    f = _Fixture()
    plan = f.make_plan()
    f.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b",
                    readiness="not-ready")

    result = f.service.validate(TASK_ID, plan)

    assert result.status == IMPACT_PLAN_VALIDATION_INVALID
    assert _mentions(result, "stale artifact readiness:d1 is missing from the plan")


def test_refreshed_artifact_is_not_invalidated():
    f = _Fixture()
    plan = f.make_plan()
    f.pointer.current_decision_id = "d2"  # the pointer was refreshed since planning

    result = f.service.validate(TASK_ID, plan)

    assert _mentions(result, "artifact execution_pointer:d1 no longer exists")
    assert "execution_pointer:d1" not in result.validated_actions


def test_unsupported_or_altered_action_is_invalid():
    f = _Fixture()
    plan = f.make_plan()
    auth = next(i for i in plan.items if i.artifact_type == "authorization")
    tampered = replace(plan, items=tuple(replace(i, action=INVALIDATION_INVALIDATE) if i is auth else i for i in plan.items))

    result = f.service.validate(TASK_ID, tampered)

    assert _mentions(result, "artifact authorization:d1: planned action is not what current state supports")


def test_missing_evidence_is_invalid():
    f = _Fixture()
    plan = f.make_plan()
    tampered = replace(plan, items=(replace(plan.items[0], evidence_required=()),) + plan.items[1:])

    result = f.service.validate(TASK_ID, tampered)

    assert _mentions(result, "names no required evidence")


def test_dependency_errors_are_invalid():
    f = _Fixture()
    plan = f.make_plan()
    reordered = replace(plan, items=tuple(reversed(plan.items)))

    result = f.service.validate(TASK_ID, reordered)

    assert _mentions(result, "which is not planned before it")


def test_manual_review_must_stay_blocking():
    f = _Fixture()
    plan = f.make_plan()
    extra = replace(
        plan.items[0], artifact_id="mystery:d1", artifact_type="mystery", action=INVALIDATION_MANUAL_REVIEW,
        mechanism=None, execution_blocked=False, depends_on=(),
    )

    result = f.service.validate(TASK_ID, replace(plan, items=plan.items + (extra,)))

    assert _mentions(result, "manual_review artifact mystery:d1 does not keep execution blocked")
    assert _mentions(result, "artifact mystery:d1 no longer exists")


def test_plan_must_match_the_authoritative_decision():
    resolution = SimpleNamespace(
        resolve=lambda task_id: SimpleNamespace(resolution_state=RESOLUTION_RESOLVED, terminal_decision_id="d9")
    )
    f = _Fixture(resolution=resolution)

    result = f.service.validate(TASK_ID, f.make_plan())

    assert _mentions(result, "the authoritative decision is now d9")


def test_ambiguous_versions_fail_closed():
    f = _Fixture()
    plan = replace(f.make_plan(), current_decision_id=None)

    result = f.service.validate(TASK_ID, plan)

    assert result.invalid and _mentions(result, "versions are ambiguous")


def test_repeated_validation_is_deterministic_and_read_only():
    f = _Fixture()
    plan = f.make_plan()
    before = (f.decision_store.history(TASK_ID), dict(f.snapshots.by_id), f.pointer.current_decision_id)

    assert f.service.validate(TASK_ID, plan) == f.service.validate(TASK_ID, plan)
    assert before == (f.decision_store.history(TASK_ID), dict(f.snapshots.by_id), f.pointer.current_decision_id)


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError):
        f.service.validate("", f.make_plan())
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationError):
        f.service.validate(TASK_ID, None)
