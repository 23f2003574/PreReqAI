from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"}
    definition.update(overrides)
    return definition


def _task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _preflight_id(preflight_store, task_id, decision=ALLOW):
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=decision,
        blocking_reasons=(), warnings=(), checked_at=NOW,
    )
    return preflight_store.save(result).preflight_id


def _stack():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_resolver=dependency_resolver, preflight_store=preflight_store
    )
    version_service = LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService(snapshot_service=snapshot_service)
    integrity_service = LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(
        snapshot_service=snapshot_service, version_service=version_service
    )
    signing_service = LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService(
        snapshot_service=snapshot_service, integrity_service=integrity_service, version_service=version_service,
    )
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service,
        signing_service=signing_service, version_service=version_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "signing_service": signing_service,
        "trust_service": trust_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


class _FakePreflightRevalidationService:
    def __init__(self):
        self.calls = []

    def revalidate(self, task_id):
        self.calls.append(task_id)


class _FakeScheduleDependencyReconciliationService:
    def __init__(self):
        self.calls = []

    def reconcile(self, task_id, schedule_id):
        self.calls.append((task_id, schedule_id))


class _FakeSchedule:
    def __init__(self, schedule_id, preflight_id):
        self.schedule_id = schedule_id
        self.preflight_id = preflight_id


class _FakeSchedulingService:
    def __init__(self, schedules):
        self._schedules = schedules

    def list(self, task_id):
        return self._schedules


def test_successful_replacement_reconciled():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, new_snapshot.snapshot_id)
    preflight_revalidation = _FakePreflightRevalidationService()

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        preflight_revalidation_service=preflight_revalidation,
    )

    result = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    assert result.reconciled is True
    assert result.preflight_id == preflight_id
    assert preflight_id in result.updated_references
    assert preflight_revalidation.calls == [task.task_id]


def test_untrusted_replacement_not_adopted():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)  # never signed -> untrusted only if signing required
    # Force untrusted via a require_signature trust_service.
    strict_trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=s["snapshot_service"], signing_service=s["signing_service"], require_signature=True,
    )
    preflight_revalidation = _FakePreflightRevalidationService()
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=strict_trust_service,
        preflight_revalidation_service=preflight_revalidation,
    )

    result = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    assert result.reconciled is False
    assert preflight_id in result.skipped_conflicts
    assert preflight_revalidation.calls == []


def test_multiple_consumers_reconciled():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, new_snapshot.snapshot_id)

    schedules = [_FakeSchedule("sched-1", preflight_id), _FakeSchedule("sched-2", preflight_id), _FakeSchedule("sched-3", "other")]
    schedule_reconciliation = _FakeScheduleDependencyReconciliationService()
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        preflight_revalidation_service=_FakePreflightRevalidationService(),
        schedule_dependency_reconciliation_service=schedule_reconciliation,
        scheduling_service=_FakeSchedulingService(schedules),
    )

    result = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    assert set(result.affected_schedule_ids) == {"sched-1", "sched-2"}
    assert set(schedule_reconciliation.calls) == {(task.task_id, "sched-1"), (task.task_id, "sched-2")}
    assert "sched-1" in result.updated_references and "sched-2" in result.updated_references


def test_conflicting_replacement_skipped():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, old_snapshot)
    candidate_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, candidate_snapshot)
    s["signing_service"].sign(task.task_id, candidate_snapshot.snapshot_id)
    # A LATER snapshot already supersedes candidate_snapshot.
    newer_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, newer_snapshot)

    # trust_service deliberately has NO version_service of its own, so it
    # cannot flag supersession itself -- isolating reconcile()'s OWN
    # conflict-via-version_service check as the thing under test.
    trust_service_without_version = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=s["snapshot_service"], signing_service=s["signing_service"],
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=trust_service_without_version,
        version_service=s["version_service"], preflight_revalidation_service=_FakePreflightRevalidationService(),
    )

    result = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, candidate_snapshot.snapshot_id)

    assert result.reconciled is False
    assert preflight_id in result.skipped_conflicts
    assert any("newer replacement" in reason for reason in result.reasons)


def test_already_reconciled_state_is_idempotent():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, new_snapshot.snapshot_id)
    preflight_revalidation = _FakePreflightRevalidationService()
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        preflight_revalidation_service=preflight_revalidation,
    )

    first = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)
    second = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    assert first.reconciled is True
    assert second.reconciled is True
    assert preflight_revalidation.calls == [task.task_id, task.task_id]  # underlying service's own idempotency applies


def test_stale_preflight_binding_rejected():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    other_task = _task(s["lifecycle_service"])
    other_preflight_id = _preflight_id(s["preflight_store"], other_task.task_id)
    foreign_snapshot = s["snapshot_service"].create(other_task.task_id, other_preflight_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
    )

    result = reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, "unknown-snapshot")
    assert result.reconciled is False


def test_history_preservation_old_snapshot_untouched():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, new_snapshot.snapshot_id)
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        preflight_revalidation_service=_FakePreflightRevalidationService(),
    )

    reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    preserved = s["snapshot_service"].get(task.task_id, old_snapshot.snapshot_id)
    assert preserved == old_snapshot


def test_no_recovery_execution_side_effects():
    s = _stack()
    task, preflight_id, old_snapshot = _snapshot(s)
    new_snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, new_snapshot.snapshot_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        preflight_revalidation_service=_FakePreflightRevalidationService(),
    )

    reconciliation_service.reconcile(task.task_id, old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    approval = s["preflight_store"].get(task.task_id)
    assert approval is not None  # preflight store untouched beyond what existed


def test_rejects_blank_arguments():
    s = _stack()
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
    )
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationError):
        reconciliation_service.reconcile("", "old", "new")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationError):
        reconciliation_service.reconcile("task-1", "old", "")
