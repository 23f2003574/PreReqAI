from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    REPLACED,
    REUSED,
    REVALIDATION_FAILED,
    REVALIDATION_MISSING,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService,
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


def _stack(require_signature=False):
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
        signing_service=signing_service, version_service=version_service, require_signature=require_signature,
    )
    revalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService(
        snapshot_service=snapshot_service, trust_service=trust_service, version_service=version_service,
        integrity_service=integrity_service, signing_service=signing_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
        "trust_service": trust_service,
        "revalidation_service": revalidation_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


def _corrupt(s, snapshot):
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def test_trusted_snapshot_is_reused():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    assert result.action == REUSED
    assert result.new_snapshot_id == snapshot.snapshot_id
    assert result.old_trust.trusted is True
    assert result.new_trust.trusted is True
    assert len(s["version_service"].list_versions(task.task_id, preflight_id)) == 0  # nothing new created


def test_invalid_snapshot_is_replaced():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)  # establish integrity baseline
    _corrupt(s, snapshot)

    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    assert result.action == REPLACED
    assert result.new_snapshot_id != snapshot.snapshot_id
    assert result.old_trust.trusted is False
    assert result.new_trust.trusted is True
    assert result.preflight_id == preflight_id


def test_integrity_and_signature_applied_to_new_snapshot():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    integrity = s["integrity_service"].verify(task.task_id, result.new_snapshot_id)
    assert integrity.status == "valid"
    signatures = s["signing_service"].list_signatures(task.task_id, result.new_snapshot_id)
    assert len(signatures) == 1


def test_version_created_for_replacement():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    versions = s["version_service"].list_versions(task.task_id, preflight_id)
    assert len(versions) == 2
    assert versions[-1].snapshot_id == result.new_snapshot_id


def test_history_preserved_old_snapshot_untouched():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    stored_old = s["snapshot_service"]._store._by_id[snapshot.snapshot_id]
    assert stored_old.dependencies[0].dependency_task_id == "ghost"  # untouched, never reverted


def test_new_snapshot_bound_to_correct_task_and_preflight():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    new_snapshot = s["snapshot_service"].get(task.task_id, result.new_snapshot_id)
    assert new_snapshot.task_id == task.task_id
    assert new_snapshot.preflight_id == preflight_id


def test_repeated_revalidation_is_idempotent():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    first = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    assert first.action == REPLACED

    second = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)
    assert second.action == REUSED
    assert second.new_snapshot_id == first.new_snapshot_id
    assert len(s["version_service"].list_versions(task.task_id, preflight_id)) == 2  # no third snapshot minted


def test_failure_safe_when_new_snapshot_also_untrusted():
    s = _stack(require_signature=True)
    task, preflight_id, snapshot = _snapshot(s)
    s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)  # baseline, still untrusted: no signature

    # revalidation_service is deliberately given NO signing_service of its
    # own, so its freshly created replacement snapshot never gets signed
    # -- while trust_service (require_signature=True) still demands one,
    # proving a genuinely failure-safe outcome rather than always
    # trivially succeeding because revalidate() signed its own output.
    revalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        version_service=s["version_service"], integrity_service=s["integrity_service"],
    )

    result = revalidation_service.revalidate(task.task_id, snapshot.snapshot_id)

    assert result.action == REVALIDATION_FAILED
    assert result.new_snapshot_id is not None
    assert result.new_trust.trusted is False


def test_missing_snapshot_reported():
    s = _stack()
    task = _task(s["lifecycle_service"])

    result = s["revalidation_service"].revalidate(task.task_id, "unknown-snapshot")

    assert result.action == REVALIDATION_MISSING
    assert result.new_snapshot_id is None
    assert result.old_trust is None


def test_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationError):
        s["revalidation_service"].revalidate("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationError):
        s["revalidation_service"].revalidate("task-1", "")
