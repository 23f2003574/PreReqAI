from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    AgentTaskRecoveryExecutionPreconditionDecision,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService,
    LLMAgentTaskRecoveryExecutionDecisionChangeImpactService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)
from lifecycle_support import _Integrity, _StatefulCalls, _executor

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


def _mentions(items, text):
    return any(text in item for item in items)


def test_fully_successful_remediation_verifies():
    f = _VerifyFixture(same_snapshot=True)

    result, verification = f.run()

    assert [o.artifact_id for o in result.applied] == ["execution_snapshot:d1", "execution_pointer:d1"]
    assert verification.valid and not verification.invalid, (verification.mismatches, verification.blocking_issues)
    assert verification.verified_artifacts == ("execution_snapshot:d1", "execution_pointer:d1")


def test_mixed_remediation_verifies_each_mechanism():
    f = _VerifyFixture()
    f.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b",
                    retry_eligibility="exhausted")

    _, verification = f.run()

    assert verification.valid, (verification.mismatches, verification.blocking_issues)
    assert {"preflight:d1", "retry_budget:d1", "authorization:d1", "execution_pointer:d1"} <= set(
        verification.verified_artifacts
    )


def test_partial_success_leaves_unresolved_artifacts_blocking():
    f = _VerifyFixture(fail={"invalidate"})

    _, verification = f.run()

    assert "preflight:d1" in verification.unresolved_artifacts
    assert "execution_snapshot:d1" in verification.unresolved_artifacts
    assert _mentions(verification.blocking_issues, "preflight:d1 (failed) remains unresolved")
    assert verification.mismatches == () and verification.invalid


def test_refresh_mismatch_is_reported():
    f = _VerifyFixture(same_snapshot=True)
    result, _ = f.run()
    f.pointer.current_decision_id = "d0"  # the pointer moved away after the operation

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert _mentions(verification.mismatches, "refreshed execution_pointer:d1 does not reference the current decision d2")


def test_invalidation_mismatch_is_reported():
    f = _VerifyFixture()
    result, _ = f.run()
    f.calls.invalidated.clear()
    f.calls.retry_scheduled = True

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert _mentions(verification.mismatches, "preflight pre-1 has no recorded invalidation")


def test_failed_integrity_after_revalidation_is_a_mismatch():
    f = _VerifyFixture(integrity=INTEGRITY_INVALID)

    _, verification = f.run()

    assert _mentions(verification.mismatches, "fails its integrity check: tampered")


def test_unresolved_manual_review_stays_blocking():
    f = _VerifyFixture(same_snapshot=True)
    plan = f.make_plan()
    manual = replace(plan.items[0], artifact_id="mystery:d1", artifact_type="mystery", action="manual_review",
                     mechanism=None, execution_blocked=True, depends_on=())

    _, verification = f.run(plan=replace(plan, items=plan.items + (manual,)))

    assert "mystery:d1" in verification.unresolved_artifacts
    assert _mentions(verification.blocking_issues, "mystery:d1 (skipped) remains unresolved")


def test_unrelated_state_mutation_is_detected():
    f = _VerifyFixture(same_snapshot=True)
    result, _ = f.run()
    f.snapshots.add("snap-2", readiness="not-ready")  # something else changed afterwards

    verification = f.verifier.verify(TASK_ID, result.operation_id)

    assert _mentions(verification.mismatches, "readiness:d1 became stale outside this operation")


def test_missing_operation_fails_closed():
    verification = _VerifyFixture().verifier.verify(TASK_ID, "no-such-operation")

    assert verification.invalid and _mentions(verification.blocking_issues, "has no audit record")


def test_repeated_verification_is_deterministic_and_read_only():
    f = _VerifyFixture()
    result, first = f.run()
    before = (f.decision_store.history(TASK_ID), dict(f.snapshots.by_id), f.pointer.current_decision_id,
              list(f.calls.log))

    second = f.verifier.verify(TASK_ID, result.operation_id)

    assert first == second
    assert before == (f.decision_store.history(TASK_ID), dict(f.snapshots.by_id), f.pointer.current_decision_id,
                      list(f.calls.log))


@pytest.mark.parametrize("args", [("", "op"), (TASK_ID, ""), (None, "op")])
def test_invalid_arguments_are_rejected(args):
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationError):
        LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService().verify(*args)
