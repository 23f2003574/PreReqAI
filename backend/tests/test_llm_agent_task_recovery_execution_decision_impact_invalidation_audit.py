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
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_FAILED,
    CONFLICT_ACTION_SKIPPED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService,
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


class _Calls:
    def __init__(self, fixture, fail=()):
        self.log, self.fixture, self.fail = [], fixture, set(fail)

    def _record(self, name):
        self.log.append(name)
        if name in self.fail:
            raise RuntimeError(f"{name} unavailable")

    def revalidate(self, task_id, snapshot_id):
        self._record(f"revalidate:{snapshot_id}")
        return SimpleNamespace(action="reused")

    def invalidate(self, task_id, reason):
        self._record("invalidate")

    def cancel_retry(self, task_id):
        self._record("cancel_retry")

    def reconcile(self, task_id):
        self._record("reconcile")
        self.fixture.pointer.current_decision_id = "d2"
        return SimpleNamespace(unresolved=())


def _executor(f, calls, **overrides):
    mechanisms = dict(
        precondition_revalidation_service=calls, preflight_invalidation_service=calls, retry_scheduler=calls,
        chain_reconciliation_service=calls,
    )
    mechanisms.update(overrides)
    return LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService(
        decision_store=f.decision_store, impact_service=f.impact, staleness_service=f.staleness,
        plan_service=f.planner, plan_validation_service=f.service, **mechanisms,
    )


def _run(f, plan=None, **kwargs):
    calls = _Calls(f, **kwargs)
    return _executor(f, calls).execute(TASK_ID, plan or f.make_plan())


def test_successful_execution_is_audited_with_exact_references():
    f = _Fixture()
    result = _run(f)
    audit = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()

    record = audit.record(TASK_ID, result)

    assert record.operation_id == result.operation_id and record.schema_version == 1
    assert (record.previous_decision_id, record.current_decision_id) == ("d1", "d2")
    assert [o.artifact_id for o in record.applied] == [o.artifact_id for o in result.applied]
    assert ("execution_pointer:d1", "stale") in record.previous_artifact_states
    assert "execution_pointer:d1" not in record.remaining_stale
    assert record.plan_valid is True and record.failed == ()
    assert (record.pre_staleness_status, record.post_staleness_status) == ("stale", "stale")
    assert record.executed_at == result.executed_at


def test_mixed_actions_are_all_captured():
    f = _Fixture()
    f.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b",
                    retry_eligibility="exhausted")

    record = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService().record(TASK_ID, _run(f))

    assert {o.action for o in record.applied} == {"revalidate", "invalidate", "refresh", "cancel"}
    assert set(record.artifact_ids) >= {o.artifact_id for o in record.applied}


def test_partial_failure_is_recorded_accurately():
    f = _Fixture()
    result = _run(f, fail={"invalidate"})

    record = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService().record(TASK_ID, result)

    (failure,) = record.failed
    assert failure.artifact_id == "preflight:d1" and "invalidate unavailable" in failure.detail
    assert any("dependencies not completed" in o.detail for o in record.skipped)
    assert {o.artifact_id for o in record.applied} >= {"authorization:d1", "execution_pointer:d1"}
    assert "preflight:d1" in record.still_blocking


def test_manual_review_blockers_are_recorded():
    f = _Fixture()
    plan = f.make_plan()
    manual = replace(plan.items[0], artifact_id="mystery:d1", artifact_type="mystery", action="manual_review",
                     mechanism=None, execution_blocked=True, depends_on=())
    result = _run(f, plan=replace(plan, items=plan.items + (manual,)))

    record = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService().record(TASK_ID, result)

    assert [o.artifact_id for o in record.manual_review] == ["mystery:d1"]
    assert record.manual_review[0] in record.skipped
    assert record.plan_valid is False and record.plan_issues


def test_duplicate_recording_is_idempotent_and_records_are_retrievable():
    f = _Fixture()
    audit = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()
    first_result = _run(f)
    second_result = _run(f)

    first = audit.record(TASK_ID, first_result)
    again = audit.record(TASK_ID, first_result)
    second = audit.record(TASK_ID, second_result)

    assert again == first and second.operation_id != first.operation_id
    assert [r.audit_id for r in audit.list(TASK_ID)] == [first.audit_id, second.audit_id]
    assert audit.get(first.audit_id) == first and audit.get("missing") is None
    assert audit.list("task-2") == []


def test_audit_never_mutates_artifacts():
    f = _Fixture()
    result = _run(f)
    before = (f.decision_store.history(TASK_ID), dict(f.snapshots.by_id), f.pointer.current_decision_id)

    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService().record(TASK_ID, result)

    assert before == (f.decision_store.history(TASK_ID), dict(f.snapshots.by_id), f.pointer.current_decision_id)


def test_invalid_arguments_are_rejected():
    f = _Fixture()
    result = _run(f)
    audit = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()
    for args in (("task-2", result), (TASK_ID, None), ("", result)):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditError):
            audit.record(*args)
