import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService, TaskDependency
from backend.agent_task_dependency_readiness_plan import (
    AgentTaskDependencyReadinessPlan,
    LLMAgentTaskDependencyReadinessService,
)
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import (
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
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    return lifecycle_service, dependency_service, resolver, plan_service


# --- fully satisfied graph -> ready plan --------------------------------------------------


def test_no_dependencies_is_ready():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)

    plan = plan_service.build_plan(task.task_id)

    assert isinstance(plan, AgentTaskDependencyReadinessPlan)
    assert plan.task_id == task.task_id
    assert plan.ready is True
    assert plan.execution_order == []
    assert plan.required_tasks == []
    assert plan.pending_tasks == []
    assert plan.blocking_tasks == []
    assert plan.failed_tasks == []
    assert plan.unresolved_tasks == []


def test_all_dependencies_completed_is_ready():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    dep_a = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep_a.task_id)
    dependency_service.add_dependency(task.task_id, dep_b.task_id)
    _advance_to(lifecycle_service, dep_a, COMPLETED)
    _advance_to(lifecycle_service, dep_b, COMPLETED)

    plan = plan_service.build_plan(task.task_id)

    assert plan.ready is True
    assert sorted(plan.execution_order) == sorted([dep_a.task_id, dep_b.task_id])
    assert plan.required_tasks == []
    assert plan.pending_tasks == []


def test_build_plan_raises_for_missing_task():
    _, _, _, plan_service = _services()

    with pytest.raises(UnknownAgentTaskError):
        plan_service.build_plan("does-not-exist")


# --- linear dependency chain -> correct order -----------------------------------------------


def test_linear_chain_execution_order_is_prerequisites_first():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.add_dependency(mid.task_id, leaf.task_id)

    plan = plan_service.build_plan(task.task_id)

    assert plan.execution_order == [leaf.task_id, mid.task_id]
    assert plan.required_tasks == [leaf.task_id, mid.task_id]
    assert plan.ready is False
    # leaf has no dependencies of its own -- it is the frontier: the
    # leading entry of required_tasks.
    assert plan.required_tasks[0] == leaf.task_id


# --- branching dependencies -> deterministic order --------------------------------------------


def test_branching_dependencies_are_ordered_deterministically():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    dep_a = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dep_c = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep_a.task_id)
    dependency_service.add_dependency(task.task_id, dep_b.task_id)
    dependency_service.add_dependency(task.task_id, dep_c.task_id)

    first = plan_service.build_plan(task.task_id)
    second = plan_service.build_plan(task.task_id)

    assert first == second
    assert first.execution_order == sorted([dep_a.task_id, dep_b.task_id, dep_c.task_id])


def test_branching_dependencies_order_independent_of_insertion_order():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)

    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, leaf.task_id)
    dependency_service.add_dependency(task.task_id, mid.task_id)

    plan = plan_service.build_plan(task.task_id)

    assert plan.execution_order == [leaf.task_id, mid.task_id]


# --- pending dependency -> correct frontier ----------------------------------------------------


def test_pending_dependency_reported_correctly():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    _advance_to(lifecycle_service, dep, RUNNING)

    plan = plan_service.build_plan(task.task_id)

    assert plan.ready is False
    assert plan.pending_tasks == [dep.task_id]
    assert plan.blocking_tasks == []
    assert plan.failed_tasks == []
    assert plan.unresolved_tasks == []
    assert plan.required_tasks == [dep.task_id]


def test_frontier_advances_once_leaf_completes():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.add_dependency(mid.task_id, leaf.task_id)
    _advance_to(lifecycle_service, leaf, COMPLETED)

    plan = plan_service.build_plan(task.task_id)

    assert plan.required_tasks == [mid.task_id]
    assert plan.pending_tasks == [mid.task_id]
    assert plan.ready is False


# --- failed / blocked dependency -> correct blocker ---------------------------------------------


def test_failed_dependency_reported_as_failed_not_blocking():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    _advance_to(lifecycle_service, dep, FAILED)

    plan = plan_service.build_plan(task.task_id)

    assert plan.ready is False
    assert plan.failed_tasks == [dep.task_id]
    assert plan.blocking_tasks == []
    assert plan.pending_tasks == []


def test_dependency_of_a_failed_dependency_is_a_blocking_task():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    failed_leaf = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, mid.task_id)
    dependency_service.add_dependency(mid.task_id, failed_leaf.task_id)
    _advance_to(lifecycle_service, failed_leaf, FAILED)

    plan = plan_service.build_plan(task.task_id)

    assert plan.ready is False
    assert plan.failed_tasks == [failed_leaf.task_id]
    assert plan.blocking_tasks == [mid.task_id]
    assert sorted(plan.required_tasks) == sorted([mid.task_id, failed_leaf.task_id])


# --- missing / cyclic graph -> explicit unresolved result -----------------------------------------


def test_missing_dependency_is_explicit_unresolved_blocker():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    dependency_service.store.save(TaskDependency(task_id=task.task_id, dependency_task_id="ghost-task"))

    plan = plan_service.build_plan(task.task_id)

    assert plan.ready is False
    assert plan.unresolved_tasks == ["ghost-task"]
    assert "ghost-task" not in plan.execution_order
    assert "ghost-task" not in plan.required_tasks


def test_cyclic_dependency_is_explicit_unresolved_blocker():
    lifecycle_service, dependency_service, resolver, plan_service = _services()
    task = _new_task(lifecycle_service)
    dep_a = _new_task(lifecycle_service)
    dep_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep_a.task_id)
    dependency_service.add_dependency(dep_a.task_id, dep_b.task_id)
    dependency_service.store.save(TaskDependency(task_id=dep_b.task_id, dependency_task_id=dep_a.task_id))

    plan = plan_service.build_plan(task.task_id)

    assert plan.ready is False
    assert sorted(plan.unresolved_tasks) == sorted([dep_a.task_id, dep_b.task_id])
    assert dep_a.task_id not in plan.execution_order
    assert dep_b.task_id not in plan.execution_order
    assert dep_a.task_id not in plan.required_tasks
