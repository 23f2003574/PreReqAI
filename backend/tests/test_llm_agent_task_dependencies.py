import pytest

from backend.agent_task_dependencies import (
    AgentTaskDependencyResult,
    CyclicDependencyError,
    DuplicateDependencyError,
    InvalidDependencyError,
    JsonTaskDependencyStore,
    LLMAgentTaskDependencyService,
    SelfDependencyError,
    TaskDependency,
    UnknownDependencyError,
)
from backend.agent_task_lifecycle import (
    CANCELLED,
    COMPLETED,
    FAILED,
    PLANNED,
    READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
    UnknownAgentTaskError,
)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _new_task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    return lifecycle_service, LLMAgentTaskDependencyService(lifecycle_service)


# --- add / remove dependency -----------------------------------------------------------


def test_add_dependency_records_edge():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)

    edge = dependency_service.add_dependency(task.task_id, prerequisite.task_id)

    assert isinstance(edge, TaskDependency)
    assert edge.task_id == task.task_id
    assert edge.dependency_task_id == prerequisite.task_id
    assert dependency_service.get_dependencies(task.task_id) == [prerequisite.task_id]
    assert dependency_service.get_dependents(prerequisite.task_id) == [task.task_id]


def test_remove_dependency_deletes_edge():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)

    dependency_service.remove_dependency(task.task_id, prerequisite.task_id)

    assert dependency_service.get_dependencies(task.task_id) == []


def test_remove_unknown_dependency_raises():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)

    with pytest.raises(UnknownDependencyError):
        dependency_service.remove_dependency(task.task_id, prerequisite.task_id)


def test_duplicate_dependency_rejected():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)

    with pytest.raises(DuplicateDependencyError):
        dependency_service.add_dependency(task.task_id, prerequisite.task_id)


# --- self-dependency rejected -----------------------------------------------------------


def test_self_dependency_rejected():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)

    with pytest.raises(SelfDependencyError):
        dependency_service.add_dependency(task.task_id, task.task_id)


# --- missing tasks -----------------------------------------------------------------------


def test_add_dependency_with_missing_task_raises():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)

    with pytest.raises(UnknownAgentTaskError):
        dependency_service.add_dependency(task.task_id, "does-not-exist")

    with pytest.raises(UnknownAgentTaskError):
        dependency_service.add_dependency("does-not-exist", task.task_id)


def test_invalid_ids_rejected():
    lifecycle_service, dependency_service = _services()

    with pytest.raises(InvalidDependencyError):
        dependency_service.add_dependency("", "task-2")
    with pytest.raises(InvalidDependencyError):
        dependency_service.get_dependencies("")


# --- cyclic dependency rejected ------------------------------------------------------------


def test_direct_cycle_rejected():
    lifecycle_service, dependency_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task_a.task_id, task_b.task_id)

    with pytest.raises(CyclicDependencyError):
        dependency_service.add_dependency(task_b.task_id, task_a.task_id)

    # The rejected edge was never recorded.
    assert dependency_service.get_dependencies(task_b.task_id) == []


def test_transitive_cycle_rejected():
    lifecycle_service, dependency_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    task_c = _new_task(lifecycle_service)
    dependency_service.add_dependency(task_a.task_id, task_b.task_id)
    dependency_service.add_dependency(task_b.task_id, task_c.task_id)

    with pytest.raises(CyclicDependencyError):
        dependency_service.add_dependency(task_c.task_id, task_a.task_id)


# --- dependency status for pending/completed/failed tasks ------------------------------------


def test_check_dependencies_satisfied_when_dependency_completed():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)
    _advance_to(lifecycle_service, prerequisite, COMPLETED)

    result = dependency_service.check_dependencies(task.task_id)

    assert isinstance(result, AgentTaskDependencyResult)
    assert result.satisfied is True
    assert result.dependencies == [prerequisite.task_id]
    assert result.pending == []
    assert result.failed == []
    assert result.blocked == []


def test_check_dependencies_pending_when_dependency_not_yet_completed():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)
    _advance_to(lifecycle_service, prerequisite, RUNNING)

    result = dependency_service.check_dependencies(task.task_id)

    assert result.satisfied is False
    assert result.pending == [prerequisite.task_id]
    assert result.failed == []
    assert result.blocked == []


def test_check_dependencies_failed_when_dependency_failed_or_cancelled():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    failed_prereq = _new_task(lifecycle_service)
    cancelled_prereq = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, failed_prereq.task_id)
    dependency_service.add_dependency(task.task_id, cancelled_prereq.task_id)
    _advance_to(lifecycle_service, failed_prereq, FAILED)
    _advance_to(lifecycle_service, cancelled_prereq, CANCELLED)

    result = dependency_service.check_dependencies(task.task_id)

    assert result.satisfied is False
    assert result.pending == []
    assert sorted(result.failed) == sorted([failed_prereq.task_id, cancelled_prereq.task_id])
    assert result.blocked == []


def test_check_dependencies_satisfied_with_no_dependencies():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)

    result = dependency_service.check_dependencies(task.task_id)

    assert result.satisfied is True
    assert result.dependencies == []


def test_check_dependencies_raises_for_missing_root_task():
    lifecycle_service, dependency_service = _services()

    with pytest.raises(UnknownAgentTaskError):
        dependency_service.check_dependencies("does-not-exist")


# --- missing dependency (structural) ------------------------------------------------------


def test_check_dependencies_reports_missing_dependency_as_blocked():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)

    # Simulate a store edited by an external process, referencing a task_id
    # that this lifecycle_service instance never created.
    dependency_service.store.save(TaskDependency(task_id=task.task_id, dependency_task_id="ghost-task"))

    result = dependency_service.check_dependencies(task.task_id)

    assert result.satisfied is False
    assert "ghost-task" in result.blocked


# --- multiple dependencies handled correctly ------------------------------------------------


def test_multiple_dependencies_mixed_states():
    lifecycle_service, dependency_service = _services()
    task = _new_task(lifecycle_service)
    completed = _new_task(lifecycle_service)
    running = _new_task(lifecycle_service)
    failed = _new_task(lifecycle_service)

    for prereq in (completed, running, failed):
        dependency_service.add_dependency(task.task_id, prereq.task_id)
    _advance_to(lifecycle_service, completed, COMPLETED)
    _advance_to(lifecycle_service, running, RUNNING)
    _advance_to(lifecycle_service, failed, FAILED)

    result = dependency_service.check_dependencies(task.task_id)

    assert result.satisfied is False
    assert sorted(result.dependencies) == sorted([completed.task_id, running.task_id, failed.task_id])
    assert result.pending == [running.task_id]
    assert result.failed == [failed.task_id]
    assert result.blocked == []


# --- multiple tasks remain isolated -----------------------------------------------------------


def test_multiple_tasks_remain_isolated():
    lifecycle_service, dependency_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    prereq_a = _new_task(lifecycle_service)
    prereq_b = _new_task(lifecycle_service)

    dependency_service.add_dependency(task_a.task_id, prereq_a.task_id)
    dependency_service.add_dependency(task_b.task_id, prereq_b.task_id)

    assert dependency_service.get_dependencies(task_a.task_id) == [prereq_a.task_id]
    assert dependency_service.get_dependencies(task_b.task_id) == [prereq_b.task_id]
    assert dependency_service.get_dependents(prereq_a.task_id) == [task_a.task_id]
    assert dependency_service.get_dependents(prereq_b.task_id) == [task_b.task_id]


def test_transitive_dependencies():
    lifecycle_service, dependency_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    task_c = _new_task(lifecycle_service)
    dependency_service.add_dependency(task_a.task_id, task_b.task_id)
    dependency_service.add_dependency(task_b.task_id, task_c.task_id)

    assert dependency_service.get_dependencies(task_a.task_id, transitive=True) == sorted(
        [task_b.task_id, task_c.task_id]
    )
    assert dependency_service.get_dependents(task_c.task_id, transitive=True) == sorted(
        [task_a.task_id, task_b.task_id]
    )


# --- JSON persistence ------------------------------------------------------------------------


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "task_dependencies.json"
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)

    service_a = LLMAgentTaskDependencyService(lifecycle_service, store=JsonTaskDependencyStore(path))
    service_a.add_dependency(task.task_id, prerequisite.task_id)

    service_b = LLMAgentTaskDependencyService(lifecycle_service, store=JsonTaskDependencyStore(path))
    assert service_b.get_dependencies(task.task_id) == [prerequisite.task_id]
