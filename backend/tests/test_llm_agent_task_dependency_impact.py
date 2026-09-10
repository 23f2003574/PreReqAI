import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService, TaskDependency
from backend.agent_task_dependency_impact import AgentTaskDependencyImpact, LLMAgentTaskDependencyImpactService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
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
    impact_service = LLMAgentTaskDependencyImpactService(lifecycle_service, dependency_service, resolver)
    return lifecycle_service, dependency_service, resolver, impact_service


# --- direct dependent impact ---------------------------------------------------------------


def test_direct_dependent_impact():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)

    impact = impact_service.analyze(task.task_id)

    assert isinstance(impact, AgentTaskDependencyImpact)
    assert impact.task_id == task.task_id
    assert impact.direct_dependents == [dependent.task_id]
    assert impact.transitive_dependents == [dependent.task_id]
    assert impact.affected_tasks == [dependent.task_id]
    assert impact.blocked_tasks == [dependent.task_id]  # task is not COMPLETED yet
    assert impact.completed_affected_tasks == []
    assert "1 direct dependent" in impact.impact_summary


def test_analyze_raises_for_missing_task():
    _, _, _, impact_service = _services()

    with pytest.raises(UnknownAgentTaskError):
        impact_service.analyze("does-not-exist")


# --- multi-level downstream impact ----------------------------------------------------------


def test_multi_level_downstream_impact():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    leaf_dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, task.task_id)
    dependency_service.add_dependency(leaf_dependent.task_id, mid.task_id)

    impact = impact_service.analyze(task.task_id)

    assert impact.direct_dependents == [mid.task_id]
    assert sorted(impact.transitive_dependents) == sorted([mid.task_id, leaf_dependent.task_id])
    assert sorted(impact.affected_tasks) == sorted([mid.task_id, leaf_dependent.task_id])
    assert sorted(impact.blocked_tasks) == sorted([mid.task_id, leaf_dependent.task_id])


# --- multiple dependency branches ------------------------------------------------------------


def test_multiple_dependency_branches():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    branch_a = _new_task(lifecycle_service)
    branch_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(branch_a.task_id, task.task_id)
    dependency_service.add_dependency(branch_b.task_id, task.task_id)

    impact = impact_service.analyze(task.task_id)

    assert sorted(impact.direct_dependents) == sorted([branch_a.task_id, branch_b.task_id])
    assert sorted(impact.transitive_dependents) == sorted([branch_a.task_id, branch_b.task_id])
    assert sorted(impact.blocked_tasks) == sorted([branch_a.task_id, branch_b.task_id])


# --- completed downstream tasks reported separately ---------------------------------------------


def test_completed_downstream_tasks_reported_separately():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    completed_dependent = _new_task(lifecycle_service)
    open_dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(completed_dependent.task_id, task.task_id)
    dependency_service.add_dependency(open_dependent.task_id, task.task_id)
    _advance_to(lifecycle_service, task, COMPLETED)
    _advance_to(lifecycle_service, completed_dependent, COMPLETED)

    impact = impact_service.analyze(task.task_id)

    assert impact.completed_affected_tasks == [completed_dependent.task_id]
    assert completed_dependent.task_id not in impact.affected_tasks
    assert completed_dependent.task_id not in impact.blocked_tasks
    assert impact.affected_tasks == [open_dependent.task_id]
    # task itself is now COMPLETED, so open_dependent's own upstream
    # dependency is satisfied -- nothing currently blocks it.
    assert impact.blocked_tasks == []


# --- already-blocked tasks handled correctly --------------------------------------------------


def test_dependent_blocked_by_an_unrelated_failed_dependency_is_still_blocked():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    other_prerequisite = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)
    dependency_service.add_dependency(dependent.task_id, other_prerequisite.task_id)
    _advance_to(lifecycle_service, task, COMPLETED)
    _advance_to(lifecycle_service, other_prerequisite, FAILED)

    impact = impact_service.analyze(task.task_id)

    # task itself is done, but dependent is still blocked -- by its
    # *other* prerequisite, which Commit #6's own resolver already
    # surfaces regardless of what specifically triggered this analysis.
    assert impact.blocked_tasks == [dependent.task_id]
    assert impact.affected_tasks == [dependent.task_id]


def test_dependent_already_failed_on_its_own_is_affected_but_not_blocked():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)
    _advance_to(lifecycle_service, dependent, FAILED)

    impact = impact_service.analyze(task.task_id)

    assert impact.affected_tasks == [dependent.task_id]
    assert impact.blocked_tasks == []
    assert impact.completed_affected_tasks == []


def test_dependent_already_cancelled_on_its_own_is_affected_but_not_blocked():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)
    _advance_to(lifecycle_service, dependent, CANCELLED)

    impact = impact_service.analyze(task.task_id)

    assert impact.affected_tasks == [dependent.task_id]
    assert impact.blocked_tasks == []


# --- no dependents -> empty impact ------------------------------------------------------------


def test_no_dependents_produces_empty_impact():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)

    impact = impact_service.analyze(task.task_id)

    assert impact.direct_dependents == []
    assert impact.transitive_dependents == []
    assert impact.affected_tasks == []
    assert impact.blocked_tasks == []
    assert impact.completed_affected_tasks == []
    assert "0 direct dependent" in impact.impact_summary


# --- cyclic / malformed graphs handled safely --------------------------------------------------


def test_cyclic_downstream_graph_handled_safely():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependent_a = _new_task(lifecycle_service)
    dependent_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent_a.task_id, task.task_id)
    dependency_service.add_dependency(dependent_b.task_id, dependent_a.task_id)
    # Force a cycle directly into the store, bypassing add_dependency()'s
    # own write-time guard -- the same defensive scenario Commit #5/#6
    # already protect against.
    dependency_service.store.save(TaskDependency(task_id=dependent_a.task_id, dependency_task_id=dependent_b.task_id))

    impact = impact_service.analyze(task.task_id)  # must not raise or hang

    assert sorted(impact.transitive_dependents) == sorted([dependent_a.task_id, dependent_b.task_id])
    assert set(impact.affected_tasks) <= {dependent_a.task_id, dependent_b.task_id}


def test_malformed_dependent_edge_to_a_missing_task_handled_safely():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependency_service.store.save(TaskDependency(task_id="ghost-dependent", dependency_task_id=task.task_id))

    impact = impact_service.analyze(task.task_id)  # must not raise

    assert "ghost-dependent" in impact.transitive_dependents
    assert "ghost-dependent" in impact.affected_tasks
    assert "ghost-dependent" in impact.blocked_tasks
    assert "ghost-dependent" not in impact.completed_affected_tasks


# --- determinism -------------------------------------------------------------------------------


def test_analyze_is_deterministic_across_repeated_calls():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)

    first = impact_service.analyze(task.task_id)
    second = impact_service.analyze(task.task_id)

    assert first == second


def test_analyze_does_not_mutate_any_task():
    lifecycle_service, dependency_service, resolver, impact_service = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)

    before_task = lifecycle_service.get(task.task_id)
    before_dependent = lifecycle_service.get(dependent.task_id)
    impact_service.analyze(task.task_id)
    after_task = lifecycle_service.get(task.task_id)
    after_dependent = lifecycle_service.get(dependent.task_id)

    assert before_task == after_task
    assert before_dependent == after_dependent
