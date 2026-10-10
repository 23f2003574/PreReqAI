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
    INDETERMINATE,
    UNCHANGED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustChangeError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService,
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

    event_store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    history_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService(
        event_service=event_service, query_service=query_service
    )
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service,
        signing_service=signing_service, version_service=version_service, history_service=history_service,
    )
    trust_change_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService(
        trust_service=trust_service, history_service=history_service
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
        "history_service": history_service,
        "trust_service": trust_service,
        "trust_change_service": trust_change_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


def test_first_check_no_prior_history():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)

    result = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    assert result.previous_trust is None
    assert result.changed is False
    assert result.changed_dimensions == ()
    assert result.revalidation_required is True


def test_unchanged_trust_between_checks():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)
    result = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    assert result.changed is False
    assert result.changed_dimensions == ()
    assert result.current_trust.trusted is True
    assert result.revalidation_required is False
    assert s["trust_change_service"].has_changed(task.task_id, snapshot.snapshot_id) is False


def test_detects_integrity_corruption():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline while trusted

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    result = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    assert result.changed is True
    assert "integrity_status" in result.changed_dimensions
    assert "trusted" in result.changed_dimensions
    assert result.current_trust.trusted is False
    assert result.revalidation_required is True
    assert any("integrity_status" in item for item in result.evidence)


def test_detects_signature_invalidation():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline while trusted

    forged = replace(record, signature="hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000")
    s["signing_service"]._store.save(forged)

    result = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    assert result.changed is True
    assert "signature_status" in result.changed_dimensions
    assert result.current_trust.trusted is False


def test_detects_version_change():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    snapshot_b = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_b)
    s["signing_service"].sign(task.task_id, snapshot_b.snapshot_id)
    s["trust_change_service"].check(task.task_id, snapshot_b.snapshot_id)

    result = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)
    assert result.changed is True
    assert result.current_trust.version == 1
    assert result.current_trust.trusted is False  # superseded by snapshot_b's version 2


def test_detects_supersession():
    s = _stack()
    task, preflight_id, snapshot_a = _snapshot(s)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_a)
    s["signing_service"].sign(task.task_id, snapshot_a.snapshot_id)
    s["trust_change_service"].check(task.task_id, snapshot_a.snapshot_id)  # trusted, latest

    snapshot_b = s["snapshot_service"].create(task.task_id, preflight_id)
    s["version_service"].create_version(task.task_id, preflight_id, snapshot_b)

    result = s["trust_change_service"].check(task.task_id, snapshot_a.snapshot_id)

    assert result.changed is True
    assert "trusted" in result.changed_dimensions
    assert result.current_trust.trusted is False
    assert any("superseded" in reason for reason in result.current_trust.blocking_reasons)


def test_repeated_checks_are_consistent():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    first = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)
    second = s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)

    assert first.changed == second.changed == False
    assert first.revalidation_required == second.revalidation_required == False


def test_validate_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustChangeError):
        s["trust_change_service"].check("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustChangeError):
        s["trust_change_service"].check("task-1", "")


def test_reconciliation_gated_by_trust_change():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_change_service"].check(task.task_id, snapshot.snapshot_id)  # establish baseline while trusted-ish

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], trust_change_service=s["trust_change_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == INDETERMINATE
    assert "not trusted" in result.reason


def test_reconciliation_proceeds_when_trust_unchanged_and_trusted():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService(
        snapshot_service=s["snapshot_service"], trust_change_service=s["trust_change_service"]
    )

    result = reconciliation_service.reconcile(task.task_id, snapshot.snapshot_id)

    assert result.status == UNCHANGED
