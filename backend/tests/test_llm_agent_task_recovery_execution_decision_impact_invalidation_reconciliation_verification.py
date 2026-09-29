from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    AgentTaskRecoveryExecutionPreconditionDecision,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    INTEGRITY_VALID,
    RESOLUTION_RESOLVED,
    IMPACT_RECONCILIATION_REPLACED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService,
    LLMAgentTaskRecoveryExecutionDecisionChangeImpactService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)
from lifecycle_support import _Integrity, _StatefulCalls, _executor, _lifecycle

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


class _Recon(_Setup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        calls = self.f.calls

        def reconcile(task_id):  # the pointer follows whatever is authoritative now
            calls.log.append("reconcile")
            self.f.pointer.current_decision_id = self.chain[-1]
            return SimpleNamespace(unresolved=())

        calls.reconcile = reconcile
        self.service = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationService(
            lifecycle_result_service=self.results, lifecycle_verification_service=self.verifier,
            lifecycle_service=self.lifecycle, resolution_service=self.resolution, impact_service=self.f.impact,
            staleness_service=self.f.staleness,
        )

    def add_decision(self, decision_id, minutes, **snapshot_overrides):
        snapshot_id = f"snap-{decision_id}"
        self.f.snapshots.add(snapshot_id, **snapshot_overrides)
        self.f.decision_store.save(
            AgentTaskRecoveryExecutionPreconditionDecision(
                task_id=TASK_ID, snapshot_id=snapshot_id, authorization_id="auth-1", decision=EXECUTION_DECISION_ALLOW,
                reason="test", blocking_conditions=(), warnings=(), validation_result=None,
                drift_classification=None, approval_reconciliation=None, created_at=T0 + timedelta(minutes=minutes),
                decision_id=decision_id,
            )
        )
        self.chain.append(decision_id)


class _Verify(_Recon):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultService()
        self.checker = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationService(
            reconciliation_result_service=self.store, lifecycle_result_service=self.results,
            lifecycle_verification_service=self.verifier, resolution_service=self.resolution,
            impact_service=self.f.impact, staleness_service=self.f.staleness,
        )

    def reconcile(self, result_id):
        return self.store.record(TASK_ID, self.service.reconcile(TASK_ID, result_id))


def _mentions(items, text):
    return any(text in item for item in items)


def test_no_op_reconciliation_verifies():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    persisted = v.reconcile(lifecycle.result_id)

    result = v.checker.verify(TASK_ID, persisted.result_id)

    assert result.valid and not result.invalid, (result.mismatches, result.missing_evidence)
    assert result.authoritative_lifecycle_result_id == lifecycle.result_id


def test_replacement_lifecycle_verifies():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    v.add_decision("d3", 10)
    persisted = v.reconcile(lifecycle.result_id)

    result = v.checker.verify(TASK_ID, persisted.result_id)

    assert persisted.state == IMPACT_RECONCILIATION_REPLACED
    assert result.valid, (result.mismatches, result.missing_evidence)
    assert result.authoritative_lifecycle_result_id == persisted.replacement_result_id


def test_stale_artifact_recurrence_is_verified():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    v.f.snapshots.add("snap-2", readiness="not-ready")
    persisted = v.reconcile(lifecycle.result_id)

    result = v.checker.verify(TASK_ID, persisted.result_id)

    assert "readiness:d1" in persisted.newly_stale_artifacts
    assert result.valid, (result.mismatches, result.missing_evidence)


def test_superseded_newest_reconciliation_is_flagged():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    persisted = v.reconcile(lifecycle.result_id)
    v.add_decision("d3", 10)  # the decision moved on after the reconciliation was recorded

    result = v.checker.verify(TASK_ID, persisted.result_id)

    assert _mentions(result.mismatches, "presents decision d2 as current, but the authoritative decision is now d3")
    assert result.authoritative_lifecycle_result_id is None


def test_missing_previous_result_fails_closed():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    reconciliation = v.service.reconcile(TASK_ID, lifecycle.result_id)
    persisted = v.store.record(TASK_ID, replace(reconciliation, previous_result_id="gone"))

    result = v.checker.verify(TASK_ID, persisted.result_id)
    unknown = v.checker.verify(TASK_ID, "no-such-reconciliation")

    assert _mentions(result.missing_evidence, "previous lifecycle result gone no longer exists")
    assert result.invalid and unknown.invalid


def test_invalid_replacement_reference_is_reported():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    v.add_decision("d3", 10)
    reconciliation = v.service.reconcile(TASK_ID, lifecycle.result_id)
    bogus = v.store.record(TASK_ID, replace(reconciliation, replacement_result_id="missing-result"))
    self_ref = v.store.record(TASK_ID, replace(reconciliation, reconciliation_id="r-2",
                                               replacement_result_id=lifecycle.result_id))

    assert _mentions(v.checker.verify(TASK_ID, bogus.result_id).missing_evidence,
                     "replacement lifecycle result missing-result does not exist")
    assert _mentions(v.checker.verify(TASK_ID, self_ref.result_id).mismatches,
                     "the replacement lifecycle result is the previous result itself")


def test_blocker_mismatch_is_reported():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    reconciliation = v.service.reconcile(TASK_ID, lifecycle.result_id)
    forged = v.store.record(TASK_ID, replace(reconciliation, unresolved_blockers=("invented blocker",)))

    result = v.checker.verify(TASK_ID, forged.result_id)

    assert _mentions(result.mismatches, "recorded unresolved blockers do not match current evidence")


def test_repeated_verification_is_deterministic_and_read_only():
    v = _Verify(same_snapshot=True)
    lifecycle, _ = v.run()
    v.add_decision("d3", 10)
    persisted = v.reconcile(lifecycle.result_id)
    before = (v.results.history(TASK_ID), v.store.history(TASK_ID), list(v.f.calls.log),
              v.f.pointer.current_decision_id)

    first = v.checker.verify(TASK_ID, persisted.result_id)
    second = v.checker.verify(TASK_ID, persisted.result_id)

    assert first == second
    assert before == (v.results.history(TASK_ID), v.store.history(TASK_ID), list(v.f.calls.log),
                      v.f.pointer.current_decision_id)


def test_invalid_arguments_are_rejected():
    v = _Verify()
    for args in (("", "r"), (TASK_ID, ""), (None, "r")):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationError):
            v.checker.verify(*args)
