from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventQueryService, LLMAgentTaskEventService
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    REPLACED,
    REUSED,
    REVALIDATION_FAILED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService,
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

    event_store = InMemoryAgentTaskEventStore()
    audit_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService(
        event_service=LLMAgentTaskEventService(store=event_store),
        query_service=LLMAgentTaskEventQueryService(store=event_store),
    )
    revalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService(
        snapshot_service=snapshot_service, trust_service=trust_service, version_service=version_service,
        integrity_service=integrity_service, signing_service=signing_service, audit_service=audit_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
        "trust_service": trust_service,
        "audit_service": audit_service,
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


def test_successful_replacement_recorded():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    records = s["audit_service"].get(task.task_id, snapshot.snapshot_id)
    assert len(records) >= 1
    record = records[-1]
    assert record.action == REPLACED
    assert record.old_snapshot_id == snapshot.snapshot_id
    assert record.new_snapshot_id == result.new_snapshot_id
    assert record.preflight_id == preflight_id
    assert record.old_trusted is False
    assert record.new_trusted is True


def test_trusted_reuse_recorded():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    record = s["audit_service"].get(task.task_id, snapshot.snapshot_id)[-1]
    assert record.action == REUSED
    assert record.new_snapshot_id == snapshot.snapshot_id
    assert record.old_trusted is True
    assert record.new_trusted is True


def test_failed_revalidation_recorded():
    s = _stack(require_signature=True)
    task, preflight_id, snapshot = _snapshot(s)
    s["integrity_service"].verify(task.task_id, snapshot.snapshot_id)

    revalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService(
        snapshot_service=s["snapshot_service"], trust_service=s["trust_service"],
        version_service=s["version_service"], integrity_service=s["integrity_service"],
        audit_service=s["audit_service"],
    )

    result = revalidation_service.revalidate(task.task_id, snapshot.snapshot_id)
    assert result.action == REVALIDATION_FAILED

    record = s["audit_service"].get(task.task_id, snapshot.snapshot_id)[-1]
    assert record.action == REVALIDATION_FAILED
    assert record.new_trusted is False
    assert record.reason is not None


def test_duplicate_recording_is_idempotent():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    first = s["audit_service"].record(task.task_id, snapshot.snapshot_id, result)
    second = s["audit_service"].record(task.task_id, snapshot.snapshot_id, result)

    assert first.audit_id == second.audit_id
    assert len(s["audit_service"].get(task.task_id, snapshot.snapshot_id)) == 1


def test_exact_identity_linkage():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    other_task = _task(s["lifecycle_service"])
    result = s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError):
        s["audit_service"].record(other_task.task_id, snapshot.snapshot_id, result)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError):
        s["audit_service"].record(task.task_id, snapshot.snapshot_id, "not-a-result")


def test_immutable_history_across_multiple_revalidations():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)  # establish baseline, REUSED
    _corrupt(s, snapshot)
    s["revalidation_service"].revalidate(task.task_id, snapshot.snapshot_id)  # REPLACED

    records = s["audit_service"].get(task.task_id, snapshot.snapshot_id)
    assert len(records) == 2
    assert records[0].action == REUSED
    assert records[1].action == REPLACED
    # Re-fetching returns the exact same, unchanged first entry.
    assert s["audit_service"].get(task.task_id, snapshot.snapshot_id)[0] == records[0]

    all_for_task = s["audit_service"].list(task.task_id)
    assert len(all_for_task) == 2


def test_get_and_list_reject_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError):
        s["audit_service"].get("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError):
        s["audit_service"].list("")
