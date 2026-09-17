from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_events import InMemoryAgentTaskEventStore, LLMAgentTaskEventQueryService, LLMAgentTaskEventService
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightInvalidationService, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    NO_OP,
    REPLACED,
    AgentTaskDependencySnapshotEntry,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationService,
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService,
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
    trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=snapshot_service, integrity_service=integrity_service,
        signing_service=signing_service, version_service=version_service,
    )
    event_store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    trust_history_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService(
        event_service=event_service, query_service=query_service
    )
    trust_change_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService(
        trust_service=trust_service, history_service=trust_history_service
    )
    preflight_invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    trust_invalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService(
        snapshot_service=snapshot_service, trust_change_service=trust_change_service,
        preflight_store=preflight_store, preflight_invalidation_service=preflight_invalidation_service,
    )
    audit_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService(
        event_service=event_service, query_service=query_service
    )
    trust_revalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService(
        snapshot_service=snapshot_service, trust_service=trust_service, version_service=version_service,
        integrity_service=integrity_service, signing_service=signing_service,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService(
        snapshot_service=snapshot_service, trust_service=trust_service, version_service=version_service,
    )
    orchestration_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationService(
        trust_change_service=trust_change_service, trust_invalidation_service=trust_invalidation_service,
        trust_revalidation_service=trust_revalidation_service, audit_service=audit_service,
        reconciliation_service=reconciliation_service,
    )
    return {
        "lifecycle_service": lifecycle_service,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
        "version_service": version_service,
        "signing_service": signing_service,
        "preflight_invalidation_service": preflight_invalidation_service,
        "audit_service": audit_service,
        "orchestration_service": orchestration_service,
    }


def _snapshot(s):
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    return task, preflight_id, snapshot


def _corrupt(s, snapshot):
    tampered = replace(snapshot, dependencies=(AgentTaskDependencySnapshotEntry(dependency_task_id="ghost", state="ready"),))
    s["snapshot_service"]._store._by_id[snapshot.snapshot_id] = tampered


def test_valid_snapshot_is_no_op():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["signing_service"].sign(task.task_id, snapshot.snapshot_id)

    result = s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    assert result.action == NO_OP
    assert result.trusted is True
    assert result.new_snapshot_id == snapshot.snapshot_id
    assert result.invalidation is None
    assert result.revalidation is None
    assert result.reconciliation is None


def test_trust_loss_triggers_full_replacement_pipeline():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)  # establish baseline
    _corrupt(s, snapshot)

    result = s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    assert result.action == REPLACED
    assert result.trusted is True
    assert result.new_snapshot_id != snapshot.snapshot_id
    assert result.invalidation is not None and result.invalidation.invalidated is True
    assert result.revalidation is not None and result.revalidation.action == REPLACED
    assert result.audit_record is not None
    assert result.reconciliation is not None and result.reconciliation.reconciled is True


def test_replacement_trust_failure_skips_reconciliation():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    strict_trust_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService(
        snapshot_service=s["snapshot_service"], signing_service=s["signing_service"], require_signature=True,
    )
    revalidation_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService(
        snapshot_service=s["snapshot_service"], trust_service=strict_trust_service,
    )
    orchestration_service = LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationService(
        trust_change_service=LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService(trust_service=strict_trust_service),
        trust_invalidation_service=LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService(
            snapshot_service=s["snapshot_service"],
            trust_change_service=LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService(trust_service=strict_trust_service),
            preflight_store=s["preflight_store"], preflight_invalidation_service=s["preflight_invalidation_service"],
        ),
        trust_revalidation_service=revalidation_service, audit_service=s["audit_service"],
    )

    result = orchestration_service.recover(task.task_id, snapshot.snapshot_id)

    assert result.trusted is False
    assert result.reconciliation is None  # fail-closed: never reconciled an untrusted replacement


def test_multiple_affected_consumers_reported():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    class _FakeSchedule:
        def __init__(self, schedule_id, preflight_id):
            self.schedule_id = schedule_id
            self.preflight_id = preflight_id

    class _FakeSchedulingService:
        def list(self, task_id):
            return [_FakeSchedule("sched-1", preflight_id), _FakeSchedule("sched-2", preflight_id)]

    s["orchestration_service"]._trust_invalidation_service._scheduling_service = _FakeSchedulingService()

    result = s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    assert set(result.invalidation.affected_schedule_ids) == {"sched-1", "sched-2"}


def test_repeated_execution_is_idempotent():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    first = s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    second = s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    assert first.new_snapshot_id == second.new_snapshot_id
    assert second.trusted is True


def test_audit_linkage():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    result = s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    audit_records = s["audit_service"].get(task.task_id, snapshot.snapshot_id)
    assert result.audit_record in audit_records
    assert result.audit_record.new_snapshot_id == result.new_snapshot_id


def test_history_preservation_old_snapshot_untouched():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    stored_old = s["snapshot_service"]._store._by_id[snapshot.snapshot_id]
    assert stored_old.dependencies[0].dependency_task_id == "ghost"  # untouched, never reverted


def test_recovery_execution_never_triggered():
    s = _stack()
    task, preflight_id, snapshot = _snapshot(s)
    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)
    _corrupt(s, snapshot)

    s["orchestration_service"].recover(task.task_id, snapshot.snapshot_id)

    # No approval/authorization/schedule was ever created for the
    # replacement preflight -- proving recover() never dispatches/
    # executes recovery itself, only prepares trusted dependency evidence.
    from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightApprovalService

    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(preflight_store=s["preflight_store"])
    assert approval_service.get(task.task_id, preflight_id) is None


def test_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationError):
        s["orchestration_service"].recover("", "snapshot-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationError):
        s["orchestration_service"].recover("task-1", "")
