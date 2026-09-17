from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService,
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
    integrity_service = LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService(snapshot_service=snapshot_service)
    signing_service = LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService(
        snapshot_service=snapshot_service, integrity_service=integrity_service,
    )
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service, signing_service=signing_service,
    )
    trust_change_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService(trust_service=trust_service)
    preflight_invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    trust_invalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService(
        snapshot_service=snapshot_service, trust_change_service=trust_change_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
        "trust_change_service": trust_change_service,
        "preflight_invalidation_service": preflight_invalidation_service,
        "trust_invalidation_service": trust_invalidation_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


def _corrupt(s, snapshot):
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def test_unchanged_trust_not_invalidated():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    result = s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id)

    assert result.warranted is False
    assert result.invalidated is False
    assert s["preflight_invalidation_service"].get_invalidation(preflight_id) is None


def test_trust_loss_triggers_invalidation():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline while trusted
    _corrupt(s, snapshot)

    result = s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id)

    assert result.warranted is True
    assert result.invalidated is True
    assert result.affected_preflight_ids == (preflight_id,)
    invalidation = s["preflight_invalidation_service"].get_invalidation(preflight_id)
    assert invalidation is not None
    assert invalidation.reason == result.reason


def test_invalid_signature_triggers_invalidation():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    forged = replace(record, signature="hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000")
    s["signing_service"]._store.save(forged)

    result = s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id)

    assert result.warranted is True
    assert result.invalidated is True
    assert s["preflight_invalidation_service"].get_invalidation(preflight_id) is not None


def test_already_invalidated_is_idempotent():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    first = s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id, reason="first reason")
    second = s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id, reason="second reason")

    assert first.invalidated is True
    assert second.invalidated is True
    assert first.reason == second.reason == "first reason"  # first reason stands, never overwritten


def test_multiple_referencing_schedules_reported():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    class _FakeSchedule:
        def __init__(self, schedule_id, preflight_id):
            self.schedule_id = schedule_id
            self.preflight_id = preflight_id

    class _FakeSchedulingService:
        def list(self, task_id):
            return [_FakeSchedule("sched-1", preflight_id), _FakeSchedule("sched-2", preflight_id), _FakeSchedule("sched-3", "other-preflight")]

    invalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService(
        snapshot_service=s["snapshot_service"], trust_change_service=s["trust_change_service"],
        preflight_store=s["preflight_store"], preflight_invalidation_service=s["preflight_invalidation_service"],
        scheduling_service=_FakeSchedulingService(),
    )

    result = invalidation_service.invalidate(task.task_id, snapshot.snapshot_id)

    assert set(result.affected_schedule_ids) == {"sched-1", "sched-2"}


def test_missing_snapshot_not_warranted():
    s = _stack()
    task = _task(s["lifecycle_service"])

    result = s["trust_invalidation_service"].invalidate(task.task_id, "unknown-snapshot")

    assert result.warranted is False
    assert result.invalidated is False


def test_check_never_writes():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    result = s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)

    assert result.warranted is True
    assert s["preflight_invalidation_service"].get_invalidation(preflight_id) is None


def test_history_preserved_original_snapshot_never_mutated_by_invalidation():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id)

    stored = s["snapshot_service"]._store._by_id[snapshot.snapshot_id]
    assert stored.dependencies[0].dependency_task_id == "ghost"  # untouched by invalidation itself


def test_invalidation_prevents_stale_snapshot_use_via_approval():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_invalidation_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    s["trust_invalidation_service"].invalidate(task.task_id, snapshot.snapshot_id)

    from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightApprovalService

    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(
        preflight_store=s["preflight_store"], invalidation_service=s["preflight_invalidation_service"]
    )
    with pytest.raises(Exception):
        approval_service.request(task.task_id, preflight_id)


def test_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError):
        s["trust_invalidation_service"].invalidate("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError):
        s["trust_invalidation_service"].check("task-1", "")
