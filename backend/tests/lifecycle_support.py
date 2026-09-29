"""Shared test doubles for the recovery execution decision lifecycle suites.

Only helpers that were byte-identical across several suites live here; anything
scenario-specific stays in the test module that uses it."""
from types import SimpleNamespace

from backend.agent_task_recovery_execution_precondition_snapshots import (
    INTEGRITY_VALID,
    RESOLUTION_RESOLVED,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService,
)


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


def _resolution(chain=("d1", "d2"), state=RESOLUTION_RESOLVED):
    return SimpleNamespace(
        resolve=lambda task_id: SimpleNamespace(
            resolution_state=state, terminal_decision_id=chain[-1] if chain else None, chain=chain,
        )
    )


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


def _lifecycle(f, resolution=None, **overrides):
    services = dict(
        resolution_service=resolution or _resolution(), impact_service=f.impact, staleness_service=f.staleness,
        plan_service=f.planner, plan_validation_service=f.service, execution_service=f.executor,
        audit_service=f.audit, verification_service=f.verifier,
    )
    services.update(overrides)
    return LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService(**services)
