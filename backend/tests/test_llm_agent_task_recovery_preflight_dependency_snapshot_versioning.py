from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    UNCHANGED,
    AgentTaskRecoveryPreflightDependencySnapshotVersionCollisionError,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError,
    InMemoryAgentTaskRecoveryPreflightDependencySnapshotVersionStore,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
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
    return {
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
    }


def test_first_version_is_one():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    version = s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    assert version.version == 1
    assert version.task_id == task.task_id
    assert version.preflight_id == preflight_id
    assert version.snapshot_id == snapshot.snapshot_id


def test_multiple_versions_increment_monotonically():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)

    snapshot_a = s["snapshot_service"].create(task.task_id, preflight_id)
    version_a = s["version_service"].create_version(task.task_id, preflight_id, snapshot_a)
    snapshot_b = s["snapshot_service"].create(task.task_id, preflight_id)
    version_b = s["version_service"].create_version(task.task_id, preflight_id, snapshot_b)

    assert version_a.version == 1
    assert version_b.version == 2
    assert [v.version for v in s["version_service"].list_versions(task.task_id, preflight_id)] == [1, 2]


def test_latest_version_lookup_is_deterministic():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)

    assert s["version_service"].latest_version(task.task_id, preflight_id) is None

    snapshot_a = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_a)
    snapshot_b = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_b)

    latest = s["version_service"].latest_version(task.task_id, preflight_id)
    assert latest.version == 2
    assert latest.snapshot_id == snapshot_b.snapshot_id
    # Repeated lookups agree.
    assert s["version_service"].latest_version(task.task_id, preflight_id) == latest


def test_get_version_returns_the_immutable_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    resolved = s["version_service"].get_version(task.task_id, preflight_id, 1)

    assert resolved == snapshot


def test_get_version_raises_for_unknown_version():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError):
        s["version_service"].get_version(task.task_id, preflight_id, 2)


def test_create_version_idempotent_for_same_snapshot_id():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    first = s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    second = s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    assert first == second
    assert len(s["version_service"].list_versions(task.task_id, preflight_id)) == 1


def test_store_rejects_version_collision():
    from backend.agent_task_recovery_preflight_dependency_snapshots import AgentTaskRecoveryPreflightDependencySnapshotVersion

    store = InMemoryAgentTaskRecoveryPreflightDependencySnapshotVersionStore()
    record = AgentTaskRecoveryPreflightDependencySnapshotVersion(
        task_id="task-1", preflight_id="preflight-1", version=1, snapshot_id="snap-1", created_at=NOW
    )
    store.save(record)
    duplicate = AgentTaskRecoveryPreflightDependencySnapshotVersion(
        task_id="task-1", preflight_id="preflight-1", version=1, snapshot_id="snap-2", created_at=NOW
    )

    with pytest.raises(AgentTaskRecoveryPreflightDependencySnapshotVersionCollisionError):
        store.save(duplicate)


def test_create_version_rejects_wrong_task_or_preflight_binding():
    s = _stack()
    task = _task(s["lifecycle_service"])
    other_task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    other_preflight_id = _preflight_id(s["preflight_store"], other_task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError):
        s["version_service"].create_version(other_task.task_id, other_preflight_id, snapshot)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotVersionError):
        s["version_service"].create_version(task.task_id, other_preflight_id, snapshot)


def test_list_versions_empty_for_unknown_task_or_preflight():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    assert s["version_service"].list_versions("unknown-task", preflight_id) == []
    assert s["version_service"].list_versions(task.task_id, "unknown-preflight") == []


def test_immutable_history_never_rewritten():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot_a = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_a)
    snapshot_b = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_b)

    versions = s["version_service"].list_versions(task.task_id, preflight_id)
    assert versions[0].snapshot_id == snapshot_a.snapshot_id
    assert versions[1].snapshot_id == snapshot_b.snapshot_id
    # Re-fetching version 1 still returns the original snapshot, untouched.
    assert s["version_service"].get_version(task.task_id, preflight_id, 1) == snapshot_a


def test_reconciliation_identifies_compared_snapshot_version():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert result.version == 1


def test_reconciliation_version_is_none_without_version_service():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.version is None


def test_reconciliation_version_is_none_when_snapshot_never_versioned():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], version_service=s["version_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.version is None
