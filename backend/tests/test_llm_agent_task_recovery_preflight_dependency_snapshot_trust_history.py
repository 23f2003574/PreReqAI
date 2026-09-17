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
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService,
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

    event_store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    history_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService(
        event_service=event_service, query_service=query_service
    )
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service,
        signing_service=signing_service, history_service=history_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "integrity_service": integrity_service,
        "signing_service": signing_service,
        "trust_service": trust_service,
        "history_service": history_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


def test_record_trusted_result():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    record = s["history_service"].latest(task.task_id, snapshot.snapshot_id)
    assert record is not None
    assert record.trusted is True
    assert record.preflight_id == preflight_id
    assert record.snapshot_id == snapshot.snapshot_id
    assert record.blocking_reasons == ()
    assert record.verified_at == result.validated_at


def test_record_corrupted_result():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # establish integrity baseline

    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    records = s["history_service"].get(task.task_id, snapshot.snapshot_id)
    assert any(not r.trusted for r in records)
    latest = s["history_service"].latest(task.task_id, snapshot.snapshot_id)
    assert latest.trusted is False
    assert any("integrity" in reason for reason in latest.blocking_reasons)


def test_record_invalid_signature_result():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    record = s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    forged = replace(record, signature="hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000")
    s["signing_service"]._store.save(forged)

    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    latest = s["history_service"].latest(task.task_id, snapshot.snapshot_id)
    assert latest.trusted is False
    assert latest.signature_status == "invalid"


def test_record_missing_snapshot_result():
    s = _stack()
    task = _task(s["lifecycle_service"])

    s["trust_service"].validate(task.task_id, "unknown-snapshot")

    latest = s["history_service"].latest(task.task_id, "unknown-snapshot")
    assert latest is not None
    assert latest.trusted is False
    assert latest.preflight_id is None


def test_repeated_verification_does_not_duplicate():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    records = s["history_service"].get(task.task_id, snapshot.snapshot_id)
    assert len(records) == 1


def test_latest_lookup():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)

    assert s["history_service"].latest(task.task_id, snapshot.snapshot_id) is None

    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # signature_status: missing
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)  # signature_status: valid -- distinct evidence

    records = s["history_service"].get(task.task_id, snapshot.snapshot_id)
    assert len(records) == 2
    latest = s["history_service"].latest(task.task_id, snapshot.snapshot_id)
    assert latest == records[-1]
    assert latest.signature_status == "valid"


def test_immutable_history_never_rewritten():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)

    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)
    s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    records = s["history_service"].get(task.task_id, snapshot.snapshot_id)
    assert len(records) == 2
    assert records[0].signature_status == "missing"
    assert records[1].signature_status == "valid"
    # Re-fetching returns the exact same, unchanged first entry.
    assert s["history_service"].get(task.task_id, snapshot.snapshot_id)[0] == records[0]


def test_record_rejects_mismatched_identity():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    result = s["trust_service"].validate(task.task_id, snapshot.snapshot_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError):
        s["history_service"].record("some-other-task", snapshot.snapshot_id, result)


def test_record_rejects_blank_arguments_and_wrong_type():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError):
        s["history_service"].get("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError):
        s["history_service"].record("task-1", "snapshot-1", "not-a-trust-result")
