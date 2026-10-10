from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import (
    COMPLETED,
    FAILED,
    PLANNED,
    READY as TASK_READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult, LLMAgentTaskRecoveryPreflightStore
from backend.agent_task_recovery_preflight_dependency_snapshots import (
    COMPLETED as DEP_COMPLETED,
    FAILED as DEP_FAILED,
    PENDING,
    READY,
    UNRESOLVED,
    InvalidAgentTaskRecoveryPreflightDependencySnapshotError,
    LLMAgentTaskRecoveryPreflightDependencySnapshotService,
)
from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"}
    definition.update(overrides)
    return definition


def _task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, TASK_READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


def _stack():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_resolver=dependency_resolver, preflight_store=preflight_store
    )
    return {
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "dependency_resolver": dependency_resolver,
        "preflight_store": preflight_store,
        "snapshot_service": snapshot_service,
    }


def _preflight_id(preflight_store, task_id, decision=ALLOW):
    result = AgentTaskRecoveryPreflightResult(
        task_id=task_id, plan=None, guard_result=None, decision=decision,
        blocking_reasons=(), warnings=(), checked_at=NOW,
    )
    return preflight_store.save(result).preflight_id


def test_create_binds_snapshot_to_exact_task_and_preflight():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)

    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    assert snapshot.task_id == task.task_id
    assert snapshot.preflight_id == preflight_id
    assert snapshot.dependencies == ()


def test_create_rejects_preflight_not_recorded_for_task_id():
    s = _stack()
    task = _task(s["lifecycle_service"])
    other_task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], other_task.task_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["snapshot_service"].create(task.task_id, preflight_id)


def test_create_rejects_unknown_preflight_id():
    s = _stack()
    task = _task(s["lifecycle_service"])

    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["snapshot_service"].create(task.task_id, "never-saved")


def test_create_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["snapshot_service"].create("", "preflight-1")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["snapshot_service"].create("task-1", "")


def test_create_captures_ready_pending_failed_blocked_completed_states():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]

    task = _task(lifecycle_service)
    completed_dep = _task(lifecycle_service)
    ready_dep = _task(lifecycle_service)
    pending_dep = _task(lifecycle_service)
    grandparent = _task(lifecycle_service)
    failed_dep = _task(lifecycle_service)

    dependency_service.add_dependency(task.task_id, completed_dep.task_id)
    dependency_service.add_dependency(task.task_id, ready_dep.task_id)
    dependency_service.add_dependency(task.task_id, pending_dep.task_id)
    dependency_service.add_dependency(pending_dep.task_id, grandparent.task_id)
    dependency_service.add_dependency(task.task_id, failed_dep.task_id)

    _advance_to(lifecycle_service, completed_dep, COMPLETED)
    _advance_to(lifecycle_service, failed_dep, FAILED)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    states = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert states[completed_dep.task_id] == DEP_COMPLETED
    assert states[ready_dep.task_id] == READY
    assert states[pending_dep.task_id] == PENDING
    assert states[grandparent.task_id] == READY
    assert states[failed_dep.task_id] == DEP_FAILED


def test_create_captures_unresolved_dependency():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]

    from backend.agent_task_dependencies import TaskDependency

    task = _task(lifecycle_service)
    # An edge to a task_id that was never actually created via the
    # lifecycle service, written directly to the underlying store -- the
    # same "referenced task does not exist at all" scenario
    # LLMAgentTaskDependencyResolver.resolve()'s own unresolved_dependencies
    # bucket is meant to catch.
    dependency_service.store.save(TaskDependency(task_id=task.task_id, dependency_task_id="ghost-task"))

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    states = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert states["ghost-task"] == UNRESOLVED


def test_get_returns_none_for_wrong_task_id():
    s = _stack()
    task = _task(s["lifecycle_service"])
    other_task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    assert s["snapshot_service"].get(task.task_id, snapshot.snapshot_id) == snapshot
    assert s["snapshot_service"].get(other_task.task_id, snapshot.snapshot_id) is None
    assert s["snapshot_service"].get(task.task_id, "unknown-snapshot") is None


def test_immutable_history_repeated_create_produces_distinct_snapshots():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)

    first = s["snapshot_service"].create(task.task_id, preflight_id)
    second = s["snapshot_service"].create(task.task_id, preflight_id)

    assert first.snapshot_id != second.snapshot_id
    assert s["snapshot_service"].get(task.task_id, first.snapshot_id) == first
    assert s["snapshot_service"].get(task.task_id, second.snapshot_id) == second


def test_diff_identical_graph_reports_no_changes():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert diff.changed is False
    assert diff.added == ()
    assert diff.removed == ()
    assert diff.resolved == ()
    assert diff.newly_blocked == ()
    assert diff.state_changed == ()
    assert diff.preflight_id == preflight_id


def test_diff_detects_added_dependency():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    new_dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, new_dep.task_id)

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert diff.changed is True
    assert diff.added == (new_dep.task_id,)
    assert diff.removed == ()


def test_diff_detects_removed_dependency():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)

    dependency_service.remove_dependency(task.task_id, dep.task_id)

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert diff.changed is True
    assert diff.removed == (dep.task_id,)
    assert diff.added == ()


def test_diff_detects_resolved_dependency_distinct_from_removed():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    before = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert before[dep.task_id] == READY

    _advance_to(lifecycle_service, dep, COMPLETED)

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert diff.resolved == (dep.task_id,)
    assert diff.removed == ()
    assert diff.changed is True


def test_diff_detects_newly_blocked_dependency():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    upstream = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    dependency_service.add_dependency(dep.task_id, upstream.task_id)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    before = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert before[dep.task_id] == PENDING

    _advance_to(lifecycle_service, upstream, FAILED)

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert dep.task_id in diff.newly_blocked
    assert diff.changed is True


def test_diff_detects_generic_state_change():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    before = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert before[dep.task_id] == READY

    # dep gains its own, not-yet-completed dependency -- dep itself moves
    # out of the "frontier" (READY) bucket into "waiting on something
    # else" (PENDING), a plain state_changed transition distinct from
    # both resolved (-> COMPLETED) and newly_blocked (-> BLOCKED).
    upstream = _task(lifecycle_service)
    dependency_service.add_dependency(dep.task_id, upstream.task_id)

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert diff.added == (upstream.task_id,)
    assert len(diff.state_changed) == 1
    change = diff.state_changed[0]
    assert change.dependency_task_id == dep.task_id
    assert change.previous_state == READY
    assert change.current_state == PENDING
    assert diff.resolved == ()
    assert diff.newly_blocked == ()


def test_diff_reports_missing_dependency_as_unresolved_state_change():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    from backend.agent_task_dependencies import TaskDependency

    task = _task(lifecycle_service)
    dependency_service.store.save(TaskDependency(task_id=task.task_id, dependency_task_id="ghost-task"))

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    snapshot = s["snapshot_service"].create(task.task_id, preflight_id)
    before = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert before["ghost-task"] == UNRESOLVED

    diff = s["snapshot_service"].diff(task.task_id, snapshot.snapshot_id)

    assert diff.changed is False
    assert diff.added == ()
    assert diff.removed == ()


def test_diff_raises_for_unknown_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    with pytest.raises(InvalidAgentTaskRecoveryPreflightDependencySnapshotError):
        s["snapshot_service"].diff(task.task_id, "unknown-snapshot")


def test_dual_collaborator_fallback_to_direct_dependency_service():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(
        dependency_service=dependency_service, preflight_store=preflight_store
    )

    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    preflight_id = _preflight_id(preflight_store, task.task_id)
    snapshot = snapshot_service.create(task.task_id, preflight_id)

    states = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
    assert states[dep.task_id] == PENDING


def test_no_collaborator_configured_yields_empty_snapshot():
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    snapshot_service = LLMAgentTaskRecoveryPreflightDependencySnapshotService(preflight_store=preflight_store)
    preflight_id = _preflight_id(preflight_store, "task-1")

    snapshot = snapshot_service.create("task-1", preflight_id)

    assert snapshot.dependencies == ()


class _FakeApprovalService:
    def get(self, task_id, preflight_id):
        return type("Approval", (), {"status": "approved"})()


class _FakeAuthorizationService:
    def authorize(self, task_id, preflight_id):
        return type("Authorization", (), {"authorization_id": "authorization-1"})()


class _FakeValidationService:
    def validate(self, task_id, authorization_id):
        return type("Validation", (), {"valid": True})()


def test_scheduling_integration_snapshots_dependencies_on_new_schedule():
    s = _stack()
    lifecycle_service, dependency_service = s["lifecycle_service"], s["dependency_service"]
    task = _task(lifecycle_service)
    dep = _task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=_FakeApprovalService(),
        authorization_service=_FakeAuthorizationService(),
        validation_service=_FakeValidationService(),
        dependency_snapshot_service=s["snapshot_service"],
    )

    scheduling_service.schedule(task.task_id, preflight_id)

    recorded = s["snapshot_service"]._store.list_for_task(task.task_id)
    assert len(recorded) == 1
    assert recorded[0].preflight_id == preflight_id
    states = {entry.dependency_task_id: entry.state for entry in recorded[0].dependencies}
    assert states[dep.task_id] == READY


def test_scheduling_integration_never_breaks_scheduling_when_snapshot_fails():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)

    class _FailingSnapshotService:
        def create(self, task_id, preflight_id):
            raise RuntimeError("boom")

    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=_FakeApprovalService(),
        authorization_service=_FakeAuthorizationService(),
        validation_service=_FakeValidationService(),
        dependency_snapshot_service=_FailingSnapshotService(),
    )

    schedule = scheduling_service.schedule(task.task_id, preflight_id)

    assert schedule.status == "scheduled"


def test_scheduling_integration_idempotent_reschedule_does_not_duplicate_snapshot():
    s = _stack()
    task = _task(s["lifecycle_service"])
    preflight_id = _preflight_id(s["preflight_store"], task.task_id)
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=_FakeApprovalService(),
        authorization_service=_FakeAuthorizationService(),
        validation_service=_FakeValidationService(),
        dependency_snapshot_service=s["snapshot_service"],
    )

    scheduling_service.schedule(task.task_id, preflight_id)
    scheduling_service.schedule(task.task_id, preflight_id)

    recorded = s["snapshot_service"]._store.list_for_task(task.task_id)
    assert len(recorded) == 1
