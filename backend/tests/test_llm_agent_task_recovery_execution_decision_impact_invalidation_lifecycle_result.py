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
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    RESOLUTION_RESOLVED,
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_EXECUTION_FAILED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    IMPACT_LIFECYCLE_UNSAFE,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    IMPACT_LIFECYCLE_VALIDATION_FAILED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService,
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


class _StatefulCalls(_Calls):
    """Mechanisms that also expose the state the verifier reads back."""

    def __init__(self, fixture, fail=()):
        super().__init__(fixture, fail)
        self.invalidated, self.retry_scheduled = set(), True

    def invalidate(self, task_id, reason):
        super().invalidate(task_id, reason)
        self.invalidated.add("pre-1")

    def cancel_retry(self, task_id):
        super().cancel_retry(task_id)
        self.retry_scheduled = False

    def get_invalidation(self, preflight_id):
        return SimpleNamespace(preflight_id=preflight_id) if preflight_id in self.invalidated else None

    def get_retry_schedule(self, task_id):
        return SimpleNamespace() if self.retry_scheduled else None


class _Integrity:
    def __init__(self, status=INTEGRITY_VALID):
        self.status = status

    def check(self, task_id, decision_id):
        return SimpleNamespace(status=self.status, issues=() if self.status == INTEGRITY_VALID else ("tampered",))


class _VerifyFixture(_Fixture):
    def __init__(self, same_snapshot=False, fail=(), integrity=INTEGRITY_VALID):
        super().__init__()
        if same_snapshot:
            self.snapshots.add("snap-2")
        self.calls = _StatefulCalls(self, fail=fail)
        self.executor = _executor(self, self.calls)
        self.audit = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()
        self.integrity = _Integrity(integrity)
        self.verifier = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService(
            audit_service=self.audit, decision_store=self.decision_store, impact_service=self.impact,
            staleness_service=self.staleness, snapshot_service=self.snapshots,
            preflight_invalidation_service=self.calls, retry_scheduler=self.calls, integrity_service=self.integrity,
        )

    def run(self, plan=None):
        result = self.executor.execute(TASK_ID, plan or self.make_plan())
        self.audit.record(TASK_ID, result)
        return result, self.verifier.verify(TASK_ID, result.operation_id)


def _resolution(chain=("d1", "d2"), state=RESOLUTION_RESOLVED):
    return SimpleNamespace(
        resolve=lambda task_id: SimpleNamespace(
            resolution_state=state, terminal_decision_id=chain[-1] if chain else None, chain=chain,
        )
    )


def _lifecycle(f, resolution=None, **overrides):
    services = dict(
        resolution_service=resolution or _resolution(), impact_service=f.impact, staleness_service=f.staleness,
        plan_service=f.planner, plan_validation_service=f.service, execution_service=f.executor,
        audit_service=f.audit, verification_service=f.verifier,
    )
    services.update(overrides)
    return LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService(**services)


def _record(f, **overrides):
    results = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService()
    lifecycle = _lifecycle(f, **overrides).run(TASK_ID)
    return lifecycle, results.record(TASK_ID, lifecycle), results


def test_successful_remediation_is_persisted_with_exact_references():
    f = _VerifyFixture(same_snapshot=True)

    lifecycle, record, _ = _record(f)

    assert record.status == IMPACT_LIFECYCLE_REMEDIATED
    assert (record.lifecycle_id, record.operation_id, record.audit_id) == (
        lifecycle.lifecycle_id, lifecycle.operation_id, lifecycle.audit_id,
    )
    assert (record.previous_decision_id, record.authoritative_decision_id) == ("d1", "d2")
    assert record.affected_artifacts == lifecycle.affected_artifacts
    assert record.planned_actions == lifecycle.planned_actions and record.applied == lifecycle.applied
    assert record.verification == lifecycle.verification and record.verification_status == "valid"
    assert record.completed_at == lifecycle.completed_at and record.schema_version == 1
    assert record.to_dict()["recorded_at"] == record.recorded_at.isoformat()


def test_partial_failure_is_persisted_as_blocked():
    f = _VerifyFixture(fail={"invalidate"})

    lifecycle, record, _ = _record(f)

    assert record.status == IMPACT_LIFECYCLE_BLOCKED
    assert record.failed == lifecycle.failed and "invalidate unavailable" in record.failed[0].detail
    assert record.blocking_artifacts == lifecycle.blocking_artifacts


def test_blocked_validation_lifecycle_is_persisted():
    f = _VerifyFixture()
    rejecting = SimpleNamespace(
        validate=lambda task_id, plan: SimpleNamespace(valid=False, issues=("stale plan",), blocking_actions=("x",))
    )

    _, record, _ = _record(f, plan_validation_service=rejecting)

    assert record.status == IMPACT_LIFECYCLE_VALIDATION_FAILED
    assert record.operation_id is None and record.errors == ("stale plan",)


def test_failed_verification_is_persisted_as_unsafe():
    f = _VerifyFixture(same_snapshot=True)
    failing = SimpleNamespace(
        verify=lambda task_id, op: SimpleNamespace(status="invalid", mismatches=("audit disagrees",), blocking_issues=())
    )

    _, record, _ = _record(f, verification_service=failing)

    assert record.status == IMPACT_LIFECYCLE_UNSAFE and record.verification_status == "invalid"


def test_duplicate_recording_and_latest_history_retrieval():
    f = _VerifyFixture()
    lifecycle = _lifecycle(f)
    results = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService()
    assert results.latest(TASK_ID) is None and results.history(TASK_ID) == []

    first_run = lifecycle.run(TASK_ID)
    first = results.record(TASK_ID, first_run)
    again = results.record(TASK_ID, first_run)
    second = results.record(TASK_ID, lifecycle.run(TASK_ID))

    assert again == first and second.status == IMPACT_LIFECYCLE_UP_TO_DATE
    assert [r.result_id for r in results.history(TASK_ID)] == [first.result_id, second.result_id]
    assert results.latest(TASK_ID) == second and results.get(TASK_ID, first.result_id) == first
    assert results.get("task-2", first.result_id) is None and results.get(TASK_ID, "missing") is None


def test_history_is_immutable_and_reads_are_side_effect_free():
    f = _VerifyFixture(same_snapshot=True)
    _, record, results = _record(f)

    with pytest.raises(Exception):
        record.status = IMPACT_LIFECYCLE_CLEAN
    snapshot = results.history(TASK_ID)
    snapshot.clear()
    assert results.history(TASK_ID) == [record]
    assert results.get(TASK_ID, record.result_id) is not record


def test_invalid_arguments_are_rejected():
    f = _VerifyFixture(same_snapshot=True)
    lifecycle = _lifecycle(f).run(TASK_ID)
    results = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService()
    for call in (
        lambda: results.record("task-2", lifecycle), lambda: results.record(TASK_ID, None),
        lambda: results.history(""), lambda: results.get(TASK_ID, ""),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultError):
            call()
