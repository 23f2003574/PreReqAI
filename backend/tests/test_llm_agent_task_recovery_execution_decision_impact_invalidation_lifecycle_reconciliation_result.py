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
    IMPACT_RECONCILIATION_ALREADY_REPLACED,
    IMPACT_RECONCILIATION_FAILED_CLOSED,
    IMPACT_RECONCILIATION_NO_OP,
    IMPACT_RECONCILIATION_REPLACED,
    InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationService,
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


def _store():
    return LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultService()


def test_no_op_reconciliation_is_persisted():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    reconciliation = s.service.reconcile(TASK_ID, record.result_id)

    persisted = _store().record(TASK_ID, reconciliation)

    assert persisted.state == IMPACT_RECONCILIATION_NO_OP and persisted.replacement_result_id is None
    assert persisted.previous_result_id == record.result_id and persisted.previous_status == record.status
    assert persisted.reconciliation_id == reconciliation.reconciliation_id and persisted.schema_version == 1
    assert persisted.to_dict()["recorded_at"] == persisted.recorded_at.isoformat()


def test_replacement_lifecycle_link_is_preserved():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    s.add_decision("d3", 10)
    reconciliation = s.service.reconcile(TASK_ID, record.result_id)

    persisted = _store().record(TASK_ID, reconciliation)

    assert persisted.state == IMPACT_RECONCILIATION_REPLACED
    assert (persisted.previous_result_id, persisted.replacement_result_id) == (
        record.result_id, reconciliation.replacement_result_id,
    )
    assert persisted.current_decision_id == "d3"
    assert s.results.get(TASK_ID, record.result_id) == record  # original lifecycle untouched


def test_unresolved_blockers_are_persisted_exactly():
    s = _Recon(fail={"invalidate"})
    record, _ = s.run()
    s.f.snapshots.add("snap-2", authorization_id="auth-2", preflight_id="pre-2", recovery_plan="plan-b",
                      readiness="not-ready")
    reconciliation = s.service.reconcile(TASK_ID, record.result_id)

    persisted = _store().record(TASK_ID, reconciliation)

    assert persisted.unresolved_blockers == reconciliation.unresolved_blockers
    assert persisted.unresolved_blockers and persisted.newly_stale_artifacts == reconciliation.newly_stale_artifacts


def test_duplicate_recording_is_idempotent():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    reconciliation = s.service.reconcile(TASK_ID, record.result_id)
    store = _store()

    first = store.record(TASK_ID, reconciliation)

    assert store.record(TASK_ID, reconciliation) == first and len(store.history(TASK_ID)) == 1


def test_history_ordering_and_latest_state():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    store = _store()
    assert store.latest(TASK_ID) is None and store.history(TASK_ID) == []

    no_op = store.record(TASK_ID, s.service.reconcile(TASK_ID, record.result_id))
    s.add_decision("d3", 10)
    replaced = store.record(TASK_ID, s.service.reconcile(TASK_ID, record.result_id))
    already = store.record(TASK_ID, s.service.reconcile(TASK_ID, record.result_id))

    assert [r.state for r in store.history(TASK_ID)] == [
        IMPACT_RECONCILIATION_NO_OP, IMPACT_RECONCILIATION_REPLACED, IMPACT_RECONCILIATION_ALREADY_REPLACED,
    ]
    assert store.latest(TASK_ID) == already
    assert already.replacement_result_id == replaced.replacement_result_id
    assert store.get(TASK_ID, no_op.result_id) == no_op and store.get("task-2", no_op.result_id) is None


def test_historical_results_are_immutable_and_reads_side_effect_free():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    store = _store()
    persisted = store.record(TASK_ID, s.service.reconcile(TASK_ID, record.result_id))

    with pytest.raises(Exception):
        persisted.state = IMPACT_RECONCILIATION_REPLACED
    snapshot = store.history(TASK_ID)
    snapshot.clear()
    assert store.history(TASK_ID) == [persisted]
    assert store.get(TASK_ID, persisted.result_id) is not persisted


def test_invalid_arguments_are_rejected():
    s = _Recon(same_snapshot=True)
    record, _ = s.run()
    reconciliation = s.service.reconcile(TASK_ID, record.result_id)
    store = _store()
    for call in (
        lambda: store.record("task-2", reconciliation), lambda: store.record(TASK_ID, None),
        lambda: store.history(""), lambda: store.get(TASK_ID, ""),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResultError):
            call()
