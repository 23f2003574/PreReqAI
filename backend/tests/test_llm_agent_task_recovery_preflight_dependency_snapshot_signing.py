from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    INVALID,
    MISSING,
    UNCHANGED,
    VALID,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
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
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
    }


def test_valid_signing_and_verification():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    result = s["signing_service"].verify_signature(task.task_id, snapshot.snapshot_id)

    assert record.task_id == task.task_id
    assert record.snapshot_id == snapshot.snapshot_id
    assert record.signature.startswith("hmac-sha256:")
    assert result.status == VALID
    assert result.valid is True
    assert result.reasons == ()
    assert result.integrity_status == VALID


def test_verify_missing_signature():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    result = s["signing_service"].verify_signature(task.task_id, snapshot.snapshot_id)

    assert result.status == MISSING
    assert result.valid is False


def test_sign_raises_for_missing_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotSigningError):
        s["signing_service"].sign(task.task_id, "unknown-snapshot")


def test_verify_detects_modified_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)  # establish the correct baseline

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    result = s["signing_service"].verify_signature(task.task_id, snapshot.snapshot_id)

    assert result.status == INVALID
    assert result.valid is False
    assert any("integrity" in reason for reason in result.reasons)
    assert any("authenticate" in reason for reason in result.reasons)


def test_verify_detects_wrong_task_preflight_version_binding():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    # Simulate a foreign/tampered signature record bound to the wrong
    # preflight_id, injected directly via the store (bypassing sign()).
    forged = replace(record, preflight_id="some-other-preflight")
    signing_service = LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService(
        snapshot_service=s["snapshot_service"], integrity_service=s["integrity_service"],
        version_service=s["version_service"],
    )
    signing_service._store.save(forged)

    result = signing_service.verify_signature(task.task_id, snapshot.snapshot_id)

    assert result.status == INVALID
    assert any("different task/preflight/snapshot/version identity" in reason for reason in result.reasons)


def test_verify_invalid_when_signature_forged():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    forged = replace(record, signature="hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000")
    s["signing_service"]._store.save(forged)

    result = s["signing_service"].verify_signature(task.task_id, snapshot.snapshot_id)

    assert result.status == INVALID
    assert result.signature_id == forged.signature_id


def test_repeated_signing_preserves_history():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    first = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    second = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    assert first.signature_id != second.signature_id
    history = s["signing_service"].list_signatures(task.task_id, snapshot.snapshot_id)
    assert [r.signature_id for r in history] == [first.signature_id, second.signature_id]

    # verify_signature() checks the LATEST record.
    result = s["signing_service"].verify_signature(task.task_id, snapshot.snapshot_id)
    assert result.signature_id == second.signature_id
    assert result.status == VALID


def test_reconciliation_carries_signature_verdict():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], signing_service=s["signing_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
    assert result.signature is not None
    assert result.signature.status == VALID
