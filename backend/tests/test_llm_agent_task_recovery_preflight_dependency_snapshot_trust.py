from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    UNCHANGED,
    INDETERMINATE,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
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


def _stack(require_signature=False, with_signing=True):
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
    ) if with_signing else None
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service,
        signing_service=signing_service, version_service=version_service, require_signature=require_signature,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
        "trust_service": trust_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


def test_valid_trust():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    assert result.trusted is True
    assert result.blocking_reasons == ()
    assert result.task_id == task.task_id
    assert result.preflight_id == preflight_id
    assert s["trust_service"].is_trusted(task.task_id, snapshot.snapshot_id) is True


def test_corrupted_snapshot_not_trusted():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # establishes integrity baseline

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    assert result.trusted is False
    assert any("integrity" in reason for reason in result.blocking_reasons)


def test_invalid_signature_not_trusted():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    forged = replace(record, signature="hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000")
    s["signing_service"]._store.save(forged)

    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    assert result.trusted is False
    assert result.signature_status == "invalid"
    assert any("signature" in reason for reason in result.blocking_reasons)


def test_missing_signature_not_trusted_when_required():
    s = _stack(require_signature=True)
    task, preflight_id, snapshot = _snapshot(s)

    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    assert result.trusted is False
    assert result.signature_status == "missing"
    assert any("signature is required" in reason for reason in result.blocking_reasons)


def test_missing_signature_trusted_when_not_required():
    s = _stack(require_signature=False)
    task, preflight_id, snapshot = _snapshot(s)

    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    assert result.trusted is True
    assert result.signature_status == "missing"


def test_version_mismatch_supersession_not_trusted():
    s = _stack()
    task, preflight_id, snapshot_a = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_a)
    snapshot_b = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_b)
    if s["signing_service"] is not None:
        s["signing_service"].sign(task.task_id, snapshot_a.snapshot_id)

    result = s["trust_service"].validate(task.task_id, snapshot_a.snapshot_id)

    assert result.trusted is False
    assert any("superseded" in reason for reason in result.blocking_reasons)

    latest_result = s["trust_service"].validate(task.task_id, snapshot_b.snapshot_id)
    assert "superseded" not in "".join(latest_result.blocking_reasons)


def test_wrong_ownership_not_trusted():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    other_task = _task(s["lifecycle_service"])

    result = s["trust_service"].validate(other_task.task_id, snapshot.snapshot_id)

    assert result.trusted is False
    assert result.preflight_id is None
    assert result.blocking_reasons != ()


def test_unavailable_verification_not_trusted():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)

    class _ExplodingIntegrityService:
        def verify(self, task_id, snapshot_id):
            raise RuntimeError("integrity backend unreachable")

    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=s["snapshot_service"], integrity_service=_ExplodingIntegrityService(),
    )

    result = trust_service.validate(task.task_id, snapshot.snapshot_id)

    assert result.trusted is False
    assert any("unavailable" in reason for reason in result.blocking_reasons)


def test_validate_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustError):
        s["trust_service"].validate("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustError):
        s["trust_service"].validate("task-1", "")


def test_deterministic_and_idempotent():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    first = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)
    second = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    assert first.trusted == second.trusted
    assert first.blocking_reasons == second.blocking_reasons


def test_reconciliation_gated_by_trust():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # establish baseline while valid

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == INDETERMINATE
    assert "not trusted" in result.reason


def test_reconciliation_proceeds_when_trusted():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
