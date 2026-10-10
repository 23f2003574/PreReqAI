import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService, TaskDependency
from backend.agent_task_dependency_resolution import (
    AgentTaskDependencyResolution,
    LLMAgentTaskDependencyResolver,
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
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    return lifecycle_service, dependency_service, resolver


# --- direct dependency resolution -------------------------------------------------------


def test_direct_dependency_resolution():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    prerequisite = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)
    _advance_to(lifecycle_service, prerequisite, COMPLETED)

    resolution = resolver.resolve(task.task_id)

    assert isinstance(resolution, AgentTaskDependencyResolution)
    assert resolution.task_id == task.task_id
    assert resolution.ordered_dependencies == [prerequisite.task_id]
    assert resolution.ready_dependencies == []
    assert resolution.pending_dependencies == []
    assert resolution.failed_dependencies == []
    assert resolution.blocked_dependencies == []
    assert resolution.unresolved_dependencies == []
    assert resolution.cycles == []


def test_resolve_raises_for_missing_root_task():
    _, _, resolver = _services()

    with pytest.raises(UnknownAgentTaskError):
        resolver.resolve("does-not-exist")


# --- multi-level / transitive dependencies ------------------------------------------------


def test_transitive_dependency_chain_orders_prerequisites_first():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.add_dependency(mid.task_id, leaf.task_id)

    resolution = resolver.resolve(task.task_id)

    assert set(resolution.ordered_dependencies) == {mid.task_id, leaf.task_id}
    assert resolution.ordered_dependencies.index(leaf.task_id) < resolution.ordered_dependencies.index(mid.task_id)
    # leaf has no dependencies of its own -- it is the frontier.
    assert resolution.ready_dependencies == [leaf.task_id]
    # mid is still waiting on leaf.
    assert resolution.pending_dependencies == [mid.task_id]


def test_frontier_advances_once_leaf_completes():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.add_dependency(mid.task_id, leaf.task_id)
    _advance_to(lifecycle_service, leaf, COMPLETED)

    resolution = resolver.resolve(task.task_id)

    assert resolution.ready_dependencies == [mid.task_id]
    assert resolution.pending_dependencies == []
    assert resolution.ordered_dependencies == [leaf.task_id, mid.task_id]


# --- deterministic ordering ---------------------------------------------------------------


def test_ordering_is_deterministic_across_repeated_calls():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    dep_a = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dep_c = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep_a.task_id)
    dependency_service.add_dependency(task.task_id, dep_b.task_id)
    dependency_service.add_dependency(task.task_id, dep_c.task_id)

    first = resolver.resolve(task.task_id)
    second = resolver.resolve(task.task_id)

    assert first == second
    # No edges among dep_a/dep_b/dep_c themselves: alphabetical tie-break.
    assert first.ordered_dependencies == sorted([dep_a.task_id, dep_b.task_id, dep_c.task_id])


def test_ordering_identical_regardless_of_edge_insertion_order():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service_1 = LLMAgentTaskDependencyService(lifecycle_service)
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf = _new_task(lifecycle_service)
    dependency_service_1.add_dependency(mid.task_id, leaf.task_id)
    dependency_service_1.add_dependency(task.task_id, mid.task_id)
    resolver_1 = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service_1)

    resolution = resolver_1.resolve(task.task_id)

    assert resolution.ordered_dependencies == [leaf.task_id, mid.task_id]


# --- pending / failed / blocked classification --------------------------------------------


def test_failed_and_cancelled_dependencies_classified_as_failed():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    failed_dep = _new_task(lifecycle_service)
    cancelled_dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, failed_dep.task_id)
    dependency_service.add_dependency(task.task_id, cancelled_dep.task_id)
    _advance_to(lifecycle_service, failed_dep, FAILED)
    _advance_to(lifecycle_service, cancelled_dep, CANCELLED)

    resolution = resolver.resolve(task.task_id)

    assert sorted(resolution.failed_dependencies) == sorted([failed_dep.task_id, cancelled_dep.task_id])
    assert resolution.blocked_dependencies == []


def test_dependency_of_a_failed_dependency_is_blocked_not_failed():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    failed_leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.add_dependency(mid.task_id, failed_leaf.task_id)
    _advance_to(lifecycle_service, failed_leaf, FAILED)

    resolution = resolver.resolve(task.task_id)

    assert resolution.failed_dependencies == [failed_leaf.task_id]
    assert resolution.blocked_dependencies == [mid.task_id]
    assert resolution.pending_dependencies == []
    assert resolution.ready_dependencies == []
    # A blocked node is still real and orderable.
    assert set(resolution.ordered_dependencies) == {mid.task_id, failed_leaf.task_id}


# --- missing dependency detection -----------------------------------------------------------


def test_missing_dependency_reported_as_unresolved():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, _new_task(lifecycle_service).task_id)
    # Simulate a store edited outside Commit #5, referencing a task that
    # was never actually created.
    dependency_service.store.save(TaskDependency(task_id=task.task_id, dependency_task_id="ghost-task"))

    resolution = resolver.resolve(task.task_id)

    assert "ghost-task" in resolution.unresolved_dependencies
    assert "ghost-task" not in resolution.ordered_dependencies


def test_dependency_of_a_missing_dependency_is_blocked():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.store.save(TaskDependency(task_id=mid.task_id, dependency_task_id="ghost-task"))

    resolution = resolver.resolve(task.task_id)

    assert resolution.unresolved_dependencies == ["ghost-task"]
    assert resolution.blocked_dependencies == [mid.task_id]


# --- cycle detection ---------------------------------------------------------------------


def test_cycle_detected_and_excluded_from_order():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    dep_a = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep_a.task_id)
    dependency_service.add_dependency(dep_a.task_id, dep_b.task_id)
    # Force a cycle dep_a <-> dep_b directly into the store, bypassing
    # add_dependency()'s own write-time cycle guard (the same defensive
    # scenario Commit #5's own check_dependencies() already protects
    # against: a store edited outside this service).
    dependency_service.store.save(TaskDependency(task_id=dep_b.task_id, dependency_task_id=dep_a.task_id))

    resolution = resolver.resolve(task.task_id)

    assert sorted(resolution.cycles) == sorted([dep_a.task_id, dep_b.task_id])
    assert dep_a.task_id not in resolution.ordered_dependencies
    assert dep_b.task_id not in resolution.ordered_dependencies
    assert dep_a.task_id not in resolution.pending_dependencies
    assert dep_a.task_id not in resolution.blocked_dependencies


def test_add_dependency_itself_still_rejects_cycles():
    lifecycle_service, dependency_service, resolver = _services()
    dep_a = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(dep_a.task_id, dep_b.task_id)

    from backend.agent_task_dependencies import CyclicDependencyError

    with pytest.raises(CyclicDependencyError):
        dependency_service.add_dependency(dep_b.task_id, dep_a.task_id)


# --- independent branches resolve correctly -------------------------------------------------


def test_independent_branches_resolve_correctly():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)
    branch_a = _new_task(lifecycle_service)
    branch_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, branch_a.task_id)
    dependency_service.add_dependency(task.task_id, branch_b.task_id)
    _advance_to(lifecycle_service, branch_a, COMPLETED)
    _advance_to(lifecycle_service, branch_b, RUNNING)

    resolution = resolver.resolve(task.task_id)

    assert set(resolution.ordered_dependencies) == {branch_a.task_id, branch_b.task_id}
    assert resolution.ready_dependencies == [branch_b.task_id]
    assert resolution.pending_dependencies == []
    assert resolution.failed_dependencies == []
    assert resolution.blocked_dependencies == []


def test_no_dependencies_resolves_trivially():
    lifecycle_service, dependency_service, resolver = _services()
    task = _new_task(lifecycle_service)

    resolution = resolver.resolve(task.task_id)

    assert resolution.ordered_dependencies == []
    assert resolution.ready_dependencies == []
    assert resolution.pending_dependencies == []
    assert resolution.failed_dependencies == []
    assert resolution.blocked_dependencies == []
    assert resolution.unresolved_dependencies == []
    assert resolution.cycles == []
