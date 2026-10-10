from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import (
    COMPLETED,
    FAILED,
    PLANNED,
    READY as TASK_READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CHANGED,
    INDETERMINATE,
    UNCHANGED,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"}
    definition.update(overrides)
    return definition


def _task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, TASK_READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


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
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=snapshot_service
    )
    return {
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "reconciliation_service": reconciliation_service,
    }


def test_reconcile_unchanged_graph():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert result.reliable is True
    assert result.reason is None
    assert result.added == result.removed == result.resolved == result.blocked == result.changed == ()
    assert result.preflight_id == preflight_id
    assert s["reconciliation_service"].is_current(task.task_id, snapshot.snapshot_id) is True


def test_reconcile_detects_addition():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    new_dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, new_dep.task_id)

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == CHANGED
    assert result.added == (new_dep.task_id,)
    assert s["reconciliation_service"].is_current(task.task_id, snapshot.snapshot_id) is False


def test_reconcile_detects_removal():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    dependency_service.remove_dependency(task.task_id, dep.task_id)

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == CHANGED
    assert result.removed == (dep.task_id,)


def test_reconcile_detects_resolved_and_blocked_state_changes():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    resolves = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    upstream = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, resolves.task_id)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    dependency_service.add_dependency(dep.task_id, upstream.task_id)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    _advance_to(lifecycle_service, resolves, COMPLETED)
    _advance_to(lifecycle_service, upstream, FAILED)

    result = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == CHANGED
    assert result.resolved == (resolves.task_id,)
    assert dep.task_id in result.blocked


def test_reconcile_indeterminate_when_dependency_resolution_fails():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    class _ExplodingResolver:
        def resolve(self, task_id):
            raise RuntimeError("dependency store unavailable")

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=LLMAgentTaskRecoveryPreflightDependencySnapshotService(
            dependency_resolver=_ExplodingResolver(), preflight_store=s["preflight_store"],
            store=s["snapshot_service"]._store,
        )
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == INDETERMINATE
    assert result.reliable is False
    assert "dependency store unavailable" in result.reason
    assert result.added == result.removed == result.resolved == result.blocked == result.changed == ()
    assert reconciliation_service.is_current(task.task_id, snapshot.snapshot_id) is False


def test_reconcile_is_repeatable_and_idempotent():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    first = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)
    second = s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    assert first.status == second.status == UNCHANGED
    assert first.added == second.added
    assert first.removed == second.removed


def test_reconcile_never_mutates_snapshot():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    before = snapshot.dependencies

    new_dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, new_dep.task_id)
    s["reconciliation_service"].reconcile(task.task_id, snapshot.snapshot_id)

    after = s["snapshot_service"].get(task.task_id, snapshot.snapshot_id)
    assert after.dependencies == before


def test_reconcile_exact_task_snapshot_binding():
    s = _stack()
    task = _task(s["lifecycle_service"])
    other_task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["reconciliation_service"].reconcile(other_task.task_id, snapshot.snapshot_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["reconciliation_service"].reconcile(task.task_id, "unknown-snapshot")


def test_reconcile_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["reconciliation_service"].reconcile("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["reconciliation_service"].reconcile("task-1", "")


def test_reconcile_for_schedule_combines_optional_collaborator():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    class _FakeScheduleDependencyReconciliationService:
        def reconcile(self, task_id, schedule_id):
            return {"task_id": task_id, "schedule_id": schedule_id, "ready": True}

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"],
        schedule_dependency_reconciliation_service=_FakeScheduleDependencyReconciliationService(),
    )

    combined = reconciliation_service.reconcile_for_schedule(task.task_id, "schedule-1", snapshot.snapshot_id)

    assert combined["snapshot"].status == UNCHANGED
    assert combined["schedule"] == {"task_id": task.task_id, "schedule_id": "schedule-1", "ready": True}


def test_reconcile_for_schedule_without_collaborator_leaves_schedule_none():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    combined = s["reconciliation_service"].reconcile_for_schedule(task.task_id, "schedule-1", snapshot.snapshot_id)

    assert combined["schedule"] is None
    assert combined["snapshot"].status == UNCHANGED
