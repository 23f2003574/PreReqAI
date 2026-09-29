from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    AgentTaskRecoveryExecutionPreconditionDecision,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_FAILED,
    CONFLICT_ACTION_SKIPPED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError,
    LLMAgentTaskRecoveryExecutionDecisionChangeImpactService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)
from lifecycle_support import _Calls, _executor

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


def _outcomes(result):
    return {o.artifact_type: o for o in result.applied + result.skipped + result.failed}


def test_each_supported_action_is_delegated_to_its_mechanism():
    f = _Fixture()
    f.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b",
                    retry_eligibility="exhausted")
    calls = _Calls(f)

    result = _executor(f, calls).execute(TASK_ID, f.make_plan())

    by_type = _outcomes(result)
    assert all(o.outcome == CONFLICT_ACTION_APPLIED for o in result.applied)
    assert by_type["authorization"].detail.startswith("precondition revalidation of snapshot snap-1")
    assert by_type["preflight"].detail == "preflight invalidated"
    assert by_type["recovery_plan"].detail == "recaptured by this run's snapshot refresh"
    assert by_type["retry_budget"].detail.startswith("retries scheduled")
    assert by_type["execution_pointer"].detail == "execution pointer reconciled"
    assert calls.log.count("revalidate:snap-1") == 2  # authorization, then the snapshot itself
    assert "invalidate" in calls.log and "cancel_retry" in calls.log and "reconcile" in calls.log


def test_stale_plan_items_are_rejected():
    f = _Fixture()
    plan = f.make_plan()
    f.pointer.current_decision_id = "d2"
    calls = _Calls(f)

    result = _executor(f, calls).execute(TASK_ID, plan)

    assert not result.plan_valid
    assert _outcomes(result)["execution_pointer"].detail == "not validated against current state"
    assert "reconcile" not in calls.log


def test_already_refreshed_artifact_is_not_mutated():
    f = _Fixture()
    plan = f.make_plan()
    calls = _Calls(f)
    # refreshed after validation, before its mutation
    original = f.service.validate
    def validate_then_refresh(task_id, p):
        result = original(task_id, p)
        f.pointer.current_decision_id = "d2"
        return result
    f.service.validate = validate_then_refresh

    result = _executor(f, calls).execute(TASK_ID, plan)

    assert _outcomes(result)["execution_pointer"].detail == "no longer stale; not mutated"
    assert "reconcile" not in calls.log


def test_manual_review_items_are_untouched():
    f = _Fixture()
    plan = f.make_plan()
    manual = replace(plan.items[0], artifact_id="mystery:d1", artifact_type="mystery", action="manual_review",
                     mechanism=None, execution_blocked=True, depends_on=())
    calls = _Calls(f)

    result = _executor(f, calls).execute(TASK_ID, replace(plan, items=plan.items + (manual,)))

    assert _outcomes(result)["mystery"].outcome == CONFLICT_ACTION_SKIPPED
    assert "left untouched and blocking" in _outcomes(result)["mystery"].detail


def test_partial_failure_keeps_successes_and_skips_dependants():
    f = _Fixture()
    calls = _Calls(f, fail={"invalidate"})

    result = _executor(f, calls).execute(TASK_ID, f.make_plan())

    by_type = _outcomes(result)
    assert by_type["authorization"].outcome == CONFLICT_ACTION_APPLIED
    assert by_type["preflight"].outcome == CONFLICT_ACTION_FAILED and "invalidate unavailable" in by_type["preflight"].detail
    assert by_type["execution_snapshot"].outcome == CONFLICT_ACTION_SKIPPED
    assert "dependencies not completed: preflight:d1" in by_type["execution_snapshot"].detail
    assert by_type["execution_pointer"].outcome == CONFLICT_ACTION_APPLIED


def test_unconfigured_mechanism_is_a_reported_failure():
    f = _Fixture()
    result = _executor(f, _Calls(f), retry_scheduler=None, preflight_invalidation_service=None).execute(
        TASK_ID, f.make_plan()
    )

    assert _outcomes(result)["preflight"].detail == "no mechanism configured for preflight"


def test_repeated_execution_is_idempotent_for_refreshed_artifacts():
    f = _Fixture()
    plan = f.make_plan()
    calls = _Calls(f)
    executor = _executor(f, calls)

    first = executor.execute(TASK_ID, plan)
    second = executor.execute(TASK_ID, plan)

    assert _outcomes(first)["execution_pointer"].outcome == CONFLICT_ACTION_APPLIED
    assert _outcomes(second)["execution_pointer"].outcome == CONFLICT_ACTION_SKIPPED
    assert calls.log.count("reconcile") == 1


def test_post_execution_staleness_is_rechecked():
    f = _Fixture()
    calls = _Calls(f)

    result = _executor(f, calls).execute(TASK_ID, f.make_plan())

    assert result.final_staleness is not None
    assert "execution_pointer:d1" not in result.still_blocking
    kinds = {a.kind: a.status for a in result.final_staleness.artifacts}
    assert kinds["execution_pointer"] == "fresh"
    # The two decisions' own snapshots still differ, so those areas stay flagged.
    assert "authorization:d1" in result.still_blocking


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    executor = _executor(f, _Calls(f))
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError):
        executor.execute("", f.make_plan())
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError):
        executor.execute(TASK_ID, None)
