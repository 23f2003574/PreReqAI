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
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError,
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


def test_clean_state_without_a_decision_change():
    f = _VerifyFixture()

    result = _lifecycle(f, resolution=_resolution(chain=("d2",))).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_CLEAN and result.authoritative_decision_id == "d2"
    assert result.operation_id is None and f.audit.list(TASK_ID) == []


def test_unresolved_authoritative_decision_fails_closed():
    f = _VerifyFixture()

    result = _lifecycle(f, resolution=_resolution(chain=(), state="rejected")).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_UNRESOLVED and f.calls.log == []


def test_successful_remediation():
    f = _VerifyFixture(same_snapshot=True)

    result = _lifecycle(f).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_REMEDIATED, (result.verification, result.errors)
    assert (result.previous_decision_id, result.authoritative_decision_id) == ("d1", "d2")
    assert [o.artifact_id for o in result.applied] == ["execution_snapshot:d1", "execution_pointer:d1"]
    assert result.audit_id == f.audit.list(TASK_ID)[0].audit_id
    assert result.verification.valid and "execution_pointer:d1" not in result.blocking_artifacts


def test_mixed_actions_are_delegated_and_blocking_areas_reported():
    f = _VerifyFixture()
    f.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b",
                    retry_eligibility="exhausted")

    result = _lifecycle(f).run(TASK_ID)

    assert {o.action for o in result.applied} == {"revalidate", "invalidate", "refresh", "cancel"}
    assert result.status == IMPACT_LIFECYCLE_REMEDIATED and result.verification.valid
    # the two decisions' own snapshots still differ, so those areas are still reported
    assert "authorization:d1" in result.remaining_stale


def test_partial_failure_is_blocked_not_successful():
    f = _VerifyFixture(fail={"invalidate"})

    result = _lifecycle(f).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_BLOCKED
    assert [o.artifact_id for o in result.failed] == ["preflight:d1"]
    assert "preflight:d1" in result.blocking_artifacts


def test_validation_failure_stops_before_execution():
    f = _VerifyFixture()
    rejecting = SimpleNamespace(
        validate=lambda task_id, plan: SimpleNamespace(valid=False, issues=("stale plan",), blocking_actions=("x",))
    )

    result = _lifecycle(f, plan_validation_service=rejecting).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_VALIDATION_FAILED and result.errors == ("stale plan",)
    assert f.calls.log == [] and f.audit.list(TASK_ID) == []


def test_verification_failure_is_unsafe():
    f = _VerifyFixture(same_snapshot=True)
    failing = SimpleNamespace(
        verify=lambda task_id, op: SimpleNamespace(mismatches=("audit disagrees",), blocking_issues=())
    )

    result = _lifecycle(f, verification_service=failing).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_UNSAFE


def test_execution_failure_is_reported():
    f = _VerifyFixture()

    def explode(task_id, plan):
        raise RuntimeError("store offline")

    result = _lifecycle(f, execution_service=SimpleNamespace(execute=explode)).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED and "store offline" in result.errors[0]


def test_unresolved_manual_review_blockers_stay_blocking():
    f = _VerifyFixture(same_snapshot=True)
    real_plan = f.planner.plan

    def with_manual(task_id, staleness):
        plan = real_plan(task_id, staleness)
        manual = replace(plan.items[0], artifact_id="mystery:d1", artifact_type="mystery", action="manual_review",
                         mechanism=None, execution_blocked=True, depends_on=())
        return replace(plan, items=plan.items + (manual,))

    result = _lifecycle(f, plan_service=SimpleNamespace(plan=with_manual)).run(TASK_ID)

    assert result.status == IMPACT_LIFECYCLE_VALIDATION_FAILED
    assert "mystery:d1" in [i.artifact_id for i in result.planned_actions]
    assert any("mystery:d1" in error for error in result.errors) and result.applied == ()


def test_repeated_execution_is_idempotent_once_remediated():
    f = _VerifyFixture()
    lifecycle = _lifecycle(f)

    first = lifecycle.run(TASK_ID)
    calls_after_first = list(f.calls.log)
    second = lifecycle.run(TASK_ID)

    assert first.status == IMPACT_LIFECYCLE_REMEDIATED and first.failed == ()
    assert second.status == IMPACT_LIFECYCLE_UP_TO_DATE and second.operation_id is None
    assert f.calls.log == calls_after_first and len(f.audit.list(TASK_ID)) == 1
    assert [d.decision_id for d in f.decision_store.history(TASK_ID)] == ["d1", "d2"]


def test_invalid_task_id_is_rejected():
    f = _VerifyFixture()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError):
        _lifecycle(f).run("")
