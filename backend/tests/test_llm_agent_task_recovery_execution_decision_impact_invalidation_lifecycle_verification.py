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
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService,
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


class _Setup:
    def __init__(self, resolution_chain=("d1", "d2"), **fixture_kwargs):
        self.f = _VerifyFixture(**fixture_kwargs)
        self.chain = list(resolution_chain)
        self.resolution = SimpleNamespace(
            resolve=lambda task_id: SimpleNamespace(
                resolution_state=RESOLUTION_RESOLVED if self.chain else "rejected",
                terminal_decision_id=self.chain[-1] if self.chain else None, chain=tuple(self.chain),
            )
        )
        self.results = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService()
        self.lifecycle = _lifecycle(self.f, resolution=self.resolution)
        self.verifier = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService(
            lifecycle_result_service=self.results, audit_service=self.f.audit,
            verification_service=self.f.verifier, resolution_service=self.resolution,
        )

    def run(self, lifecycle_result=None):
        record = self.results.record(TASK_ID, lifecycle_result or self.lifecycle.run(TASK_ID))
        return record, self.verifier.verify(TASK_ID, record.result_id)


def _mentions(items, text):
    return any(text in item for item in items)


def test_successful_lifecycle_verifies():
    s = _Setup(same_snapshot=True)

    record, result = s.run()

    assert record.status == IMPACT_LIFECYCLE_REMEDIATED
    assert result.valid and not result.invalid, (result.mismatches, result.missing_evidence)


def test_partial_remediation_is_truthful_with_blockers():
    s = _Setup(fail={"invalidate"})

    record, result = s.run()

    assert record.status == IMPACT_LIFECYCLE_BLOCKED
    assert result.valid, (result.mismatches, result.missing_evidence)
    assert "preflight:d1" in result.remaining_blockers
    assert _mentions(result.remaining_blockers, "preflight:d1 (failed) remains unresolved")


def test_stale_result_is_detected_when_the_decision_moves_on():
    s = _Setup(same_snapshot=True)
    record, _ = s.run()
    s.chain.append("d3")

    result = s.verifier.verify(TASK_ID, record.result_id)

    assert _mentions(result.mismatches, "recorded authoritative decision d2 is no longer authoritative (now d3)")


def test_artifact_mismatch_is_detected():
    s = _Setup(same_snapshot=True)
    record, _ = s.run()
    s.f.pointer.current_decision_id = "d0"

    result = s.verifier.verify(TASK_ID, record.result_id)

    assert _mentions(result.mismatches, "artifact state: refreshed execution_pointer:d1 does not reference")
    assert _mentions(result.mismatches, "recorded verification status 'valid' is inconsistent")


def test_audit_mismatch_is_detected():
    s = _Setup(same_snapshot=True)
    lifecycle = s.lifecycle.run(TASK_ID)
    forged = replace(lifecycle, audit_id="other-audit", applied=(), affected_artifacts=("mystery:d1",))

    _, result = s.run(forged)

    assert _mentions(result.mismatches, "references audit other-audit")
    assert _mentions(result.mismatches, "applied artifacts disagree with the audit record")
    assert _mentions(result.mismatches, "affected artifacts not part of the operation: mystery:d1")


def test_missing_evidence_fails_closed():
    s = _Setup(same_snapshot=True)
    lifecycle = s.lifecycle.run(TASK_ID)
    _, orphan = s.run(replace(lifecycle, operation_id="unknown-operation"))
    s.chain.clear()
    record, _ = s.run()

    unresolved = s.verifier.verify(TASK_ID, record.result_id)
    unknown = s.verifier.verify(TASK_ID, "no-such-result")

    assert _mentions(orphan.missing_evidence, "no audit record exists for operation unknown-operation")
    assert unresolved.invalid and _mentions(unresolved.missing_evidence, "authoritative decision cannot be established")
    assert unknown.invalid and _mentions(unknown.missing_evidence, "does not exist for task")


def test_success_without_passing_verification_is_a_mismatch():
    s = _Setup(same_snapshot=True)
    lifecycle = s.lifecycle.run(TASK_ID)

    _, result = s.run(replace(lifecycle, verification=None))

    assert _mentions(result.mismatches, "recorded as remediated without a passing verification")


def test_repeated_verification_is_deterministic_and_read_only():
    s = _Setup()
    record, first = s.run()
    before = (s.f.decision_store.history(TASK_ID), dict(s.f.snapshots.by_id), s.f.pointer.current_decision_id,
              list(s.f.calls.log), s.results.history(TASK_ID))

    second = s.verifier.verify(TASK_ID, record.result_id)

    assert first == second
    assert before == (s.f.decision_store.history(TASK_ID), dict(s.f.snapshots.by_id), s.f.pointer.current_decision_id,
                      list(s.f.calls.log), s.results.history(TASK_ID))


@pytest.mark.parametrize("args", [("", "r"), (TASK_ID, ""), (None, "r")])
def test_invalid_arguments_are_rejected(args):
    s = _Setup()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationError):
        s.verifier.verify(*args)
