from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    CORRUPTED,
    MISSING,
    UNCHANGED,
    VALID,
    AgentTaskDependencySnapshotEntry,
    AgentTaskRecoveryPreflightDependencySnapshotVersion,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
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
    integrity_service = LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(
        snapshot_service=snapshot_service, version_service=version_service
    )
    return {
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
    }


def test_valid_snapshot_verifies():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    result = s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)

    assert result.status == VALID
    assert result.valid is True
    assert result.reasons == ()
    assert result.integrity_value is not None
    assert result.preflight_id == preflight_id


def test_compute_is_deterministic():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    first = s["integrity_service"].compute(task.task_id, snapshot.snapshot_id)
    second = s["integrity_service"].compute(task.task_id, snapshot.snapshot_id)

    assert first == second
    assert first.startswith("sha256:")


def test_compute_raises_for_missing_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotIntegrityError):
        s["integrity_service"].compute(task.task_id, "unknown-snapshot")


def test_verify_missing_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    result = s["integrity_service"].verify(task.task_id, "unknown-snapshot")

    assert result.status == MISSING
    assert result.valid is False


def test_verify_detects_modified_content():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    baseline = s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)
    assert baseline.status == VALID

    # Simulate external tampering: overwrite the persisted snapshot's own
    # dependency content, bypassing the service layer entirely.
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    result = s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)

    assert result.status == CORRUPTED
    assert result.valid is False
    assert any("integrity value" in reason for reason in result.reasons)


def test_verify_detects_modified_metadata():
    s = _stack()
    task = _task(s["lifecycle_service"])
    other_task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    baseline = s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)
    assert baseline.status == VALID

    tampered = replace(snapshot, captured_at=snapshot.captured_at + timedelta(days=1))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    result = s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)

    assert result.status == CORRUPTED
    assert result.valid is False


def test_verify_detects_version_mismatch():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    # Simulate a corrupted version index: a second version number bound
    # to the SAME snapshot_id, bypassing create_version()'s own
    # idempotent-by-snapshot_id guard via a direct store write.
    conflicting = AgentTaskRecoveryPreflightDependencySnapshotVersion(
        task_id=task.task_id, preflight_id=preflight_id, version=2,
        snapshot_id=snapshot.snapshot_id, created_at=NOW,
    )
    s["version_service"]._store.save(conflicting)

    result = s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)

    assert result.status == CORRUPTED
    assert any("multiple version numbers" in reason for reason in result.reasons)


def test_verify_never_mutates_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)

    after = s["snapshot_service"].get(task.task_id, snapshot.snapshot_id)
    assert after == snapshot


def test_reconciliation_carries_integrity_verdict():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], integrity_service=s["integrity_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert result.integrity is not None
    assert result.integrity.status == VALID


def test_version_retrieval_rejects_corrupted_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)

    version_service = LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService(
        snapshot_service=s["snapshot_service"], store=s["version_service"]._store,
        integrity_service=s["integrity_service"],
    )
    version_service.get_version(task.task_id, preflight_id, 1)  # establishes the baseline

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    with pytest.raises(Exception):
        version_service.get_version(task.task_id, preflight_id, 1)
