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
    IMPACT_RECONCILIATION_ALREADY_REPLACED,
    IMPACT_RECONCILIATION_FAILED_CLOSED,
    IMPACT_RECONCILIATION_NO_OP,
    IMPACT_RECONCILIATION_REPLACED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationError,
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


def test_unchanged_state_is_a_no_op():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    history = s.results.history(TASK_ID)

    result = s.service.reconcile(TASK_ID, record.result_id)

    assert result.state == IMPACT_RECONCILIATION_NO_OP and result.replacement_result_id is None
    assert result.current_decision_id == "d2" and result.final_verification_status == "valid"
    assert s.results.history(TASK_ID) == history


def test_decision_change_produces_a_replacement_lifecycle():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    s.add_decision("d3", 10)

    result = s.service.reconcile(TASK_ID, record.result_id)

    assert result.state == IMPACT_RECONCILIATION_REPLACED and result.current_decision_id == "d3"
    replacement = s.results.get(TASK_ID, result.replacement_result_id)
    assert replacement.authoritative_decision_id == "d3" and replacement.previous_decision_id == "d2"
    assert result.replacement_operation_id == replacement.operation_id
    assert s.results.get(TASK_ID, record.result_id) == record  # original preserved


def test_newly_stale_artifact_triggers_a_new_operation():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    s.f.snapshots.add("snap-2", readiness="not-ready")

    result = s.service.reconcile(TASK_ID, record.result_id)

    assert "readiness:d1" in result.newly_stale_artifacts
    assert result.state == IMPACT_RECONCILIATION_REPLACED
    replacement = s.results.get(TASK_ID, result.replacement_result_id)
    assert any(o.artifact_id == "readiness:d1" for o in replacement.applied)


def test_failed_verification_of_the_replacement_is_reported():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    s.add_decision("d3", 10)
    s.f.calls.fail.add("reconcile")

    def failing_reconcile(task_id):
        raise RuntimeError("reconcile unavailable")

    s.f.calls.reconcile = failing_reconcile

    result = s.service.reconcile(TASK_ID, record.result_id)

    replacement = s.results.get(TASK_ID, result.replacement_result_id)
    assert result.state == IMPACT_RECONCILIATION_REPLACED and replacement.status != "remediated"
    assert result.unresolved_blockers


def test_missing_evidence_fails_closed():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()

    unknown = s.service.reconcile(TASK_ID, "no-such-result")
    s.chain.clear()
    unresolved = s.service.reconcile(TASK_ID, record.result_id)

    assert unknown.state == IMPACT_RECONCILIATION_FAILED_CLOSED and unknown.issues
    assert unresolved.state == IMPACT_RECONCILIATION_FAILED_CLOSED
    assert "cannot be established" in unresolved.issues[0]


def test_repeated_reconciliation_is_idempotent():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    s.add_decision("d3", 10)

    first = s.service.reconcile(TASK_ID, record.result_id)
    count = len(s.results.history(TASK_ID))
    second = s.service.reconcile(TASK_ID, record.result_id)
    third = s.service.reconcile(TASK_ID, first.replacement_result_id)

    assert first.state == IMPACT_RECONCILIATION_REPLACED
    assert second.state == IMPACT_RECONCILIATION_ALREADY_REPLACED
    assert second.replacement_result_id == first.replacement_result_id
    assert third.state == IMPACT_RECONCILIATION_NO_OP
    assert len(s.results.history(TASK_ID)) == count


def test_invalid_arguments_are_rejected():
    s = _Recon()
    for args in (("", "r"), (TASK_ID, ""), (None, "r")):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationError):
            s.service.reconcile(*args)
