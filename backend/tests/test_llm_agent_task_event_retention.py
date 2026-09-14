from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    InMemoryAgentTaskEventStore,
    InvalidAgentTaskEventRetentionError,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventProjectionService,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventRetentionService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, LLMAgentTaskLifecycleService, PLANNED


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services(**kwargs):
    event_store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=event_store)
    query_service = LLMAgentTaskEventQueryService(store=event_store)
    retention_service = LLMAgentTaskEventRetentionService(query_service=query_service, **kwargs)
    return emitter, query_service, retention_service


def _old(days=60):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _save_at(store, event, when):
    from dataclasses import replace

    store.delete(event.task_id, event.event_id)
    store.save(replace(event, occurred_at=when))


# --- old eligible events ---------------------------------------------------------------------


def test_old_events_are_eligible_by_default():
    emitter, query_service, retention_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)  # recent -- keeps task-1 "alive" but this event itself is protected as latest

    plan = retention_service.plan("task-1")

    eligible_ids = {c.event_id for c in plan.eligible}
    assert old_event.event_id in eligible_ids


def test_plan_rejects_blank_task_id():
    _, _, retention_service = _services()

    with pytest.raises(InvalidAgentTaskEventRetentionError):
        retention_service.plan(task_id="")


def test_plan_rejects_non_datetime_before():
    _, _, retention_service = _services()

    with pytest.raises(InvalidAgentTaskEventRetentionError):
        retention_service.plan(before="not-a-datetime")


# --- events inside retention window ------------------------------------------------------------


def test_recent_events_are_never_eligible():
    emitter, query_service, retention_service = _services()
    emitter.emit("task-1", CONTEXT_UPDATED)
    emitter.emit("task-1", CONTEXT_UPDATED)

    plan = retention_service.plan("task-1")

    assert plan.eligible == ()


def test_explicit_before_cutoff_is_respected():
    emitter, query_service, retention_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old(days=10))
    emitter.emit("task-1", CONTEXT_UPDATED)  # kept recent, and protected as latest anyway

    plan_default = retention_service.plan("task-1")  # default window is 30 days -- 10-day-old event is inside it
    plan_short = retention_service.plan("task-1", before=datetime.now(timezone.utc) - timedelta(days=5))

    assert old_event.event_id not in {c.event_id for c in plan_default.eligible}
    assert old_event.event_id in {c.event_id for c in plan_short.eligible}


# --- active-task protection -----------------------------------------------------------------


def test_active_task_events_are_protected():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = lifecycle_service.create(_definition())
    emitter, query_service, _ = _services()
    old_event = emitter.emit(task.task_id, CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit(task.task_id, CONTEXT_UPDATED)  # keep some recent activity too

    retention_service = LLMAgentTaskEventRetentionService(
        query_service=query_service, lifecycle_service=lifecycle_service
    )
    plan = retention_service.plan(task.task_id)

    assert old_event.event_id not in {c.event_id for c in plan.eligible}
    protected_ids = {p.event_id for p in plan.protected}
    assert old_event.event_id in protected_ids


def test_terminal_task_events_are_not_protected_by_lifecycle_check():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = lifecycle_service.create(_definition())
    lifecycle_service.transition(task.task_id, PLANNED)
    lifecycle_service.transition(task.task_id, FAILED)

    emitter, query_service, _ = _services()
    old_event = emitter.emit(task.task_id, CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit(task.task_id, CONTEXT_UPDATED)

    retention_service = LLMAgentTaskEventRetentionService(
        query_service=query_service, lifecycle_service=lifecycle_service
    )
    plan = retention_service.plan(task.task_id)

    # still not eligible: the second emit() is the "latest event" protection, but old_event
    # itself is now free of the active-task protection since the task is terminal
    eligible_ids = {c.event_id for c in plan.eligible}
    assert old_event.event_id in eligible_ids


# --- projection-required event protection ----------------------------------------------------


def test_projection_referenced_event_is_protected():
    emitter, query_service, _ = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())

    projection_service = LLMAgentTaskEventProjectionService(query_service=query_service)
    projection_service.refresh("task-1")  # captures old_event as last_event_id

    newer_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, newer_event, _old(days=45))  # also old, but not referenced by the stale projection

    retention_service = LLMAgentTaskEventRetentionService(
        query_service=query_service, projection_service=projection_service
    )
    plan = retention_service.plan("task-1", before=datetime.now(timezone.utc) - timedelta(days=1))

    protected_ids = {p.event_id for p in plan.protected}
    assert old_event.event_id in protected_ids  # referenced by the (stale) persisted projection
    # newer_event is now the latest event for the task, so it is protected too, but for a
    # different reason
    assert newer_event.event_id in protected_ids


# --- correlated/parent event protection --------------------------------------------------------


def test_referenced_parent_event_is_protected():
    emitter, query_service, retention_service = _services()
    parent = emitter.emit("task-1", LIFECYCLE_TRANSITIONED)
    _save_at(query_service.store, parent, _old())
    child = emitter.emit("task-2", CONTEXT_UPDATED, parent_event_id=parent.event_id)
    _save_at(query_service.store, child, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)  # keeps task-1 non-empty/recent
    emitter.emit("task-2", CONTEXT_UPDATED)  # so child is no longer task-2's own latest event

    plan = retention_service.plan()  # cross-task

    protected_ids = {p.event_id for p in plan.protected}
    assert parent.event_id in protected_ids
    # the child itself has no incoming reference, so it's still eligible
    eligible_ids = {c.event_id for c in plan.eligible}
    assert child.event_id in eligible_ids


# --- empty retention plan -----------------------------------------------------------------------


def test_empty_event_stream_produces_empty_plan():
    _, _, retention_service = _services()

    plan = retention_service.plan("task-1")

    assert plan.eligible == ()
    assert plan.protected == ()


# --- successful reconciliation / execute ---------------------------------------------------------


def test_execute_removes_eligible_events():
    emitter, query_service, retention_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)

    plan = retention_service.plan("task-1")
    result = retention_service.execute(plan)

    assert any(c.event_id == old_event.event_id for c in result.removed)
    remaining_ids = {e.event_id for e in query_service.query(task_id="task-1")}
    assert old_event.event_id not in remaining_ids


def test_execute_rejects_non_plan_argument():
    _, _, retention_service = _services()

    with pytest.raises(InvalidAgentTaskEventRetentionError):
        retention_service.execute("not-a-plan")


def test_execute_skips_events_that_became_protected_since_planning():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = lifecycle_service.create(_definition())
    emitter, query_service, _ = _services()
    old_event = emitter.emit(task.task_id, CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit(task.task_id, CONTEXT_UPDATED)

    retention_service = LLMAgentTaskEventRetentionService(query_service=query_service)
    plan = retention_service.plan(task.task_id)
    assert old_event.event_id in {c.event_id for c in plan.eligible}

    # simulate the task becoming newly protected between plan() and execute()
    retention_service_with_lifecycle = LLMAgentTaskEventRetentionService(
        query_service=query_service, lifecycle_service=lifecycle_service
    )
    result = retention_service_with_lifecycle.execute(plan)

    assert any(p.event_id == old_event.event_id for p in result.newly_protected)
    remaining_ids = {e.event_id for e in query_service.query(task_id=task.task_id)}
    assert old_event.event_id in remaining_ids  # never deleted


# --- repeated execution is idempotent ------------------------------------------------------------


def test_repeated_execution_is_idempotent():
    emitter, query_service, retention_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit("task-1", CONTEXT_UPDATED)

    plan = retention_service.plan("task-1")
    first = retention_service.execute(plan)
    second = retention_service.execute(plan)

    assert any(c.event_id == old_event.event_id for c in first.removed)
    assert any(c.event_id == old_event.event_id for c in second.already_removed)
    assert second.removed == ()


# --- verify protected events remain available ------------------------------------------------------


def test_protected_events_remain_queryable_after_execute():
    emitter, query_service, retention_service = _services()
    old_event = emitter.emit("task-1", CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    latest_event = emitter.emit("task-1", CONTEXT_UPDATED)

    plan = retention_service.plan("task-1")
    retention_service.execute(plan)

    remaining_ids = {e.event_id for e in query_service.query(task_id="task-1")}
    assert latest_event.event_id in remaining_ids
    assert old_event.event_id not in remaining_ids


def test_retention_service_never_mutates_authoritative_task_state():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = lifecycle_service.create(_definition())
    emitter, query_service, _ = _services()
    old_event = emitter.emit(task.task_id, CONTEXT_UPDATED)
    _save_at(query_service.store, old_event, _old())
    emitter.emit(task.task_id, CONTEXT_UPDATED)

    retention_service = LLMAgentTaskEventRetentionService(
        query_service=query_service, lifecycle_service=lifecycle_service
    )
    plan = retention_service.plan(task.task_id)
    retention_service.execute(plan)

    unchanged = lifecycle_service.get(task.task_id)
    assert unchanged.current_state == task.current_state
    assert unchanged.updated_at == task.updated_at
