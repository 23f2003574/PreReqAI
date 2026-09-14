from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventRecoveryOrchestrationError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventArchiveRecoveryService,
    LLMAgentTaskEventArchiveService,
    LLMAgentTaskEventConsistencyService,
    LLMAgentTaskEventProjectionReconciliationService,
    LLMAgentTaskEventProjectionService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventRecoveryOrchestrationService,
    LLMAgentTaskEventRetentionService,
    LLMAgentTaskEventService,
    RECOVERY_STAGE_CONSISTENCY,
    RECOVERY_STAGE_PLAN,
    RECOVERY_STAGE_PROJECTION,
    RECOVERY_STAGE_VERIFICATION,
)
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService, RUNNING


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _stack():
    active_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=active_store)
    query_service = LLMAgentTaskEventQueryService(store=active_store)
    retention_service = LLMAgentTaskEventRetentionService(query_service=query_service)
    archive_service = LLMAgentTaskEventArchiveService(retention_service=retention_service)
    recovery_service = LLMAgentTaskEventArchiveRecoveryService(
        archive_service=archive_service, active_query_service=query_service
    )

    lifecycle_service = LLMAgentTaskLifecycleService()
    consistency_service = LLMAgentTaskEventConsistencyService(lifecycle_service, query_service=query_service)

    projection_service = LLMAgentTaskEventProjectionService(query_service=query_service)
    projection_reconciliation_service = LLMAgentTaskEventProjectionReconciliationService(projection_service)

    orchestrator = LLMAgentTaskEventRecoveryOrchestrationService(
        consistency_service=consistency_service,
        recovery_service=recovery_service,
        projection_reconciliation_service=projection_reconciliation_service,
    )

    task = lifecycle_service.create(_definition())

    return SimpleNamespace(
        emitter=emitter,
        query_service=query_service,
        archive_service=archive_service,
        recovery_service=recovery_service,
        lifecycle_service=lifecycle_service,
        consistency_service=consistency_service,
        projection_reconciliation_service=projection_reconciliation_service,
        orchestrator=orchestrator,
        task=task,
    )


def _old(days=60):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _save_at(store, event, when):
    store.delete(event.task_id, event.event_id)
    store.save(replace(event, occurred_at=when))


# --- successful end-to-end recovery -----------------------------------------------------------


def test_successful_end_to_end_recovery():
    stack = _stack()
    task_id = stack.task.task_id
    old_event = stack.emitter.emit(task_id, CONTEXT_UPDATED)
    _save_at(stack.query_service.store, old_event, _old())
    stack.emitter.emit(task_id, CONTEXT_UPDATED)  # latest, stays active
    stack.archive_service.archive(task_id)

    result = stack.orchestrator.recover_task_history(task_id)

    assert result.success is True
    assert result.failure_stage is None
    assert result.recovery_result is not None
    assert old_event.event_id in result.recovery_result.restored
    assert result.verification_result is not None
    assert result.verification_result.is_valid is True
    assert result.consistency_result is not None
    assert result.consistency_result.is_consistent is True
    assert result.projection_result is not None


def test_orchestrator_rejects_blank_task_id():
    stack = _stack()

    with pytest.raises(InvalidAgentTaskEventRecoveryOrchestrationError):
        stack.orchestrator.recover_task_history("")


def test_orchestrator_rejects_non_list_event_ids():
    stack = _stack()

    with pytest.raises(InvalidAgentTaskEventRecoveryOrchestrationError):
        stack.orchestrator.recover_task_history(stack.task.task_id, event_ids="not-a-list")


# --- recovery conflict stops workflow ------------------------------------------------------------


def test_conflict_stops_workflow_at_plan_stage():
    stack = _stack()
    task_id = stack.task.task_id
    old_event = stack.emitter.emit(task_id, CONTEXT_UPDATED)
    _save_at(stack.query_service.store, old_event, _old())
    stack.emitter.emit(task_id, CONTEXT_UPDATED)
    stack.archive_service.archive(task_id)

    # introduce a conflicting active event under the same identity
    conflicting = replace(old_event, event_type=LIFECYCLE_TRANSITIONED, payload={"to_state": "planned"})
    stack.query_service.store.save(conflicting)

    result = stack.orchestrator.recover_task_history(task_id)

    assert result.success is False
    assert result.failure_stage == RECOVERY_STAGE_PLAN
    assert result.recovery_result is None
    assert result.verification_result is None
    assert result.consistency_result is None
    assert result.projection_result is None


# --- verification failure ------------------------------------------------------------------------


def test_verification_failure_stops_workflow():
    stack = _stack()
    task_id = stack.task.task_id
    good_event = stack.emitter.emit(task_id, CONTEXT_UPDATED)
    _save_at(stack.query_service.store, good_event, _old())
    broken_event = stack.emitter.emit(task_id, CONTEXT_UPDATED, parent_event_id="ghost-parent")
    _save_at(stack.query_service.store, broken_event, _old())
    stack.emitter.emit(task_id, CONTEXT_UPDATED)  # latest, stays active
    stack.archive_service.archive(task_id)

    # only recover good_event -- broken_event stays archived, but Commit #11's
    # own verify() (called with no event_ids filter inside recover()) still
    # audits the whole archive, catching its dangling parent reference
    result = stack.orchestrator.recover_task_history(task_id, event_ids=[good_event.event_id])

    assert result.success is False
    assert result.failure_stage == RECOVERY_STAGE_VERIFICATION
    assert result.recovery_result is not None
    assert result.verification_result is not None
    assert result.verification_result.is_valid is False
    assert result.consistency_result is None
    assert result.projection_result is None


# --- consistency failure --------------------------------------------------------------------------


def test_consistency_failure_stops_workflow():
    stack = _stack()
    task_id = stack.task.task_id
    stack.emitter.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": "created"})
    stack.emitter.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})  # illegal jump

    result = stack.orchestrator.recover_task_history(task_id)

    assert result.success is False
    assert result.failure_stage == RECOVERY_STAGE_CONSISTENCY
    assert result.recovery_result is not None
    assert result.verification_result is not None
    assert result.consistency_result is not None
    assert result.consistency_result.is_consistent is False
    assert result.projection_result is None


# --- projection reconciliation failure -----------------------------------------------------------


class _BrokenProjectionReconciliationService:
    def reconcile(self, task_id):
        raise RuntimeError("simulated projection backend outage")


def test_projection_reconciliation_failure_stops_workflow():
    stack = _stack()
    task_id = stack.task.task_id
    stack.emitter.emit(task_id, CONTEXT_UPDATED)

    orchestrator = LLMAgentTaskEventRecoveryOrchestrationService(
        consistency_service=stack.consistency_service,
        recovery_service=stack.recovery_service,
        projection_reconciliation_service=_BrokenProjectionReconciliationService(),
    )

    result = orchestrator.recover_task_history(task_id)

    assert result.success is False
    assert result.failure_stage == RECOVERY_STAGE_PROJECTION
    assert result.recovery_result is not None
    assert result.verification_result is not None
    assert result.consistency_result is not None
    assert result.projection_result is None


# --- idempotent repeated execution ------------------------------------------------------------------


def test_repeated_execution_is_idempotent():
    stack = _stack()
    task_id = stack.task.task_id
    old_event = stack.emitter.emit(task_id, CONTEXT_UPDATED)
    _save_at(stack.query_service.store, old_event, _old())
    stack.emitter.emit(task_id, CONTEXT_UPDATED)
    stack.archive_service.archive(task_id)

    first = stack.orchestrator.recover_task_history(task_id)
    # a second, explicitly-scoped call demonstrates the "already restored"
    # signal directly (see Commit #12's own docstring: once an event moves,
    # its archived copy is gone, so an unscoped plan simply has nothing left
    # to say about it -- naming it explicitly is how a caller re-checks it)
    second = stack.orchestrator.recover_task_history(task_id, event_ids=[old_event.event_id])

    assert first.success is True
    assert second.success is True
    assert old_event.event_id in first.recovery_result.restored
    assert old_event.event_id not in second.recovery_result.restored
    assert old_event.event_id in second.recovery_result.already_restored
    assert len(stack.query_service.query(task_id=task_id)) == 2  # never duplicated


# --- authoritative task state remains unchanged -------------------------------------------------------


def test_authoritative_task_state_is_never_modified():
    stack = _stack()
    task_id = stack.task.task_id
    old_event = stack.emitter.emit(task_id, CONTEXT_UPDATED)
    _save_at(stack.query_service.store, old_event, _old())
    stack.emitter.emit(task_id, CONTEXT_UPDATED)
    stack.archive_service.archive(task_id)

    before = stack.lifecycle_service.get(task_id)
    stack.orchestrator.recover_task_history(task_id)
    after = stack.lifecycle_service.get(task_id)

    assert after.current_state == before.current_state
    assert after.updated_at == before.updated_at
