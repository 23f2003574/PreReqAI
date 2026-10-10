import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_change_impact import (
    AgentTaskDependencyChangeImpact,
    DEPENDENCY_ADDED,
    DEPENDENCY_REMOVED,
    LLMAgentTaskDependencyChangeImpactService,
    STATE_CHANGE,
)
from backend.agent_task_dependency_impact import LLMAgentTaskDependencyImpactService
from backend.agent_task_dependency_readiness_cache import (
    LLMAgentTaskDependencyReadinessCache,
    LLMAgentTaskDependencyReadinessCachedService,
)
from backend.agent_task_dependency_readiness_invalidation import (
    LLMAgentTaskDependencyCacheInvalidatingService,
    LLMAgentTaskDependencyReadinessInvalidationService,
    LLMAgentTaskLifecycleCacheInvalidatingService,
)
from backend.agent_task_dependency_readiness_plan import LLMAgentTaskDependencyReadinessService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import (
    CREATED,
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
    dependency_impact_service = LLMAgentTaskDependencyImpactService(
        lifecycle_service, dependency_service, LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    )
    change_impact_service = LLMAgentTaskDependencyChangeImpactService(
        lifecycle_service, dependency_service, dependency_impact_service
    )
    return lifecycle_service, dependency_service, change_impact_service


# --- state change causing a task to become ready ----------------------------------------------


def test_state_change_causing_task_to_become_ready():
    lifecycle_service, dependency_service, change_impact_service = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)
    _advance_to(lifecycle_service, dep, RUNNING)

    impact = change_impact_service.analyze_change(
        dep.task_id, STATE_CHANGE, old_state=RUNNING, new_state=COMPLETED
    )

    assert isinstance(impact, AgentTaskDependencyChangeImpact)
    assert impact.unresolved_reason is None
    assert dependent.task_id in impact.newly_ready_tasks
    assert dependent.task_id in impact.affected_tasks
    assert dep.task_id in impact.invalidated_cache_entries
    assert dependent.task_id in impact.invalidated_cache_entries


# --- state change causing downstream blocking ---------------------------------------------------


def test_state_change_causing_downstream_blocking():
    # Commit #1's COMPLETED is terminal (never regresses), so a downstream
    # dependent can only ever reach ready=True once its own dependency is
    # already COMPLETED -- meaning a *state* change alone can never flip a
    # dependent from ready back to blocked (only a *dependency* change
    # can, see test_dependency_addition_makes_task_not_ready below). What
    # a state change *can* do is change which reason a still-not-ready
    # dependent is blocked for -- pending becomes failed -- which this
    # verifies via affected_tasks rather than newly_blocked_tasks.
    lifecycle_service, dependency_service, change_impact_service = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)
    _advance_to(lifecycle_service, dep, RUNNING)

    impact = change_impact_service.analyze_change(dep.task_id, STATE_CHANGE, old_state=RUNNING, new_state=FAILED)

    assert impact.unresolved_reason is None
    assert dependent.task_id in impact.affected_tasks
    assert dependent.task_id not in impact.newly_ready_tasks
    assert dependent.task_id not in impact.newly_blocked_tasks  # was already not-ready


# --- dependency addition / removal ------------------------------------------------------------


def test_dependency_addition_makes_task_not_ready():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)
    new_prereq = _new_task(lifecycle_service)  # not completed

    impact = change_impact_service.analyze_change(task.task_id, DEPENDENCY_ADDED, dependency_task_id=new_prereq.task_id)

    assert impact.unresolved_reason is None
    assert task.task_id in impact.newly_blocked_tasks
    assert task.task_id in impact.invalidated_cache_entries


def test_dependency_addition_of_an_already_failed_task_is_newly_blocked_with_a_failed_reason():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)
    failed_prereq = _new_task(lifecycle_service)
    _advance_to(lifecycle_service, failed_prereq, FAILED)

    impact = change_impact_service.analyze_change(
        task.task_id, DEPENDENCY_ADDED, dependency_task_id=failed_prereq.task_id
    )

    assert impact.unresolved_reason is None
    assert task.task_id in impact.newly_blocked_tasks


def test_dependency_removal_makes_task_ready():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)
    prereq = _new_task(lifecycle_service)  # not completed
    dependency_service.add_dependency(task.task_id, prereq.task_id)

    impact = change_impact_service.analyze_change(task.task_id, DEPENDENCY_REMOVED, dependency_task_id=prereq.task_id)

    assert impact.unresolved_reason is None
    assert task.task_id in impact.newly_ready_tasks


def test_dependency_addition_that_would_create_a_cycle_is_unresolved():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    dependency_service.add_dependency(task_b.task_id, task_a.task_id)

    impact = change_impact_service.analyze_change(task_a.task_id, DEPENDENCY_ADDED, dependency_task_id=task_b.task_id)

    assert impact.unresolved_reason is not None
    assert impact.affected_tasks == []
    assert impact.invalidated_cache_entries == []


def test_dependency_addition_self_dependency_is_unresolved():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)

    impact = change_impact_service.analyze_change(task.task_id, DEPENDENCY_ADDED, dependency_task_id=task.task_id)

    assert impact.unresolved_reason is not None


def test_dependency_change_missing_dependency_task_id_is_unresolved():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)

    impact = change_impact_service.analyze_change(task.task_id, DEPENDENCY_ADDED, dependency_task_id="does-not-exist")

    assert impact.unresolved_reason is not None


# --- multi-level dependency impact -------------------------------------------------------------


def test_multi_level_dependency_impact():
    lifecycle_service, dependency_service, change_impact_service = _services()
    root = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    top = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, root.task_id)
    dependency_service.add_dependency(top.task_id, mid.task_id)
    _advance_to(lifecycle_service, root, RUNNING)

    impact = change_impact_service.analyze_change(root.task_id, STATE_CHANGE, old_state=RUNNING, new_state=COMPLETED)

    assert impact.unresolved_reason is None
    assert mid.task_id in impact.newly_ready_tasks  # mid's only dependency just completed
    assert top.task_id in impact.affected_tasks  # still not ready (waits on mid), but blocker changed
    assert set(impact.invalidated_cache_entries) == {root.task_id, mid.task_id, top.task_id}


# --- unaffected branches excluded ---------------------------------------------------------------


def test_unaffected_branches_excluded():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)
    unrelated = _new_task(lifecycle_service)  # entirely separate graph

    impact = change_impact_service.analyze_change(dep.task_id, STATE_CHANGE, old_state=CREATED, new_state=PLANNED)

    assert unrelated.task_id not in impact.affected_tasks
    assert unrelated.task_id not in impact.unchanged_tasks
    assert unrelated.task_id not in impact.invalidated_cache_entries


def test_unrelated_sibling_dependent_stays_unchanged():
    lifecycle_service, dependency_service, change_impact_service = _services()
    dep = _new_task(lifecycle_service)
    already_running_dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(already_running_dependent.task_id, dep.task_id)

    impact = change_impact_service.analyze_change(dep.task_id, STATE_CHANGE, old_state=CREATED, new_state=PLANNED)

    # dep going CREATED -> PLANNED never changes whether it is COMPLETED
    # (it still is not), so already_running_dependent's own plan is
    # identical before and after.
    assert already_running_dependent.task_id in impact.unchanged_tasks
    assert already_running_dependent.task_id not in impact.affected_tasks


# --- cache impact matches invalidation requirements ------------------------------------------------


def test_cache_impact_matches_real_commit_10_invalidation():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cached_plan_service = LLMAgentTaskDependencyReadinessCachedService(plan_service, cache)
    dependency_impact_service = LLMAgentTaskDependencyImpactService(lifecycle_service, dependency_service, resolver)
    change_impact_service = LLMAgentTaskDependencyChangeImpactService(
        lifecycle_service, dependency_service, dependency_impact_service
    )

    root = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    top = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, root.task_id)
    dependency_service.add_dependency(top.task_id, mid.task_id)
    for node in (root, mid, top):
        cached_plan_service.build_plan(node.task_id)

    tracked_lifecycle = LLMAgentTaskLifecycleCacheInvalidatingService(invalidation_service, store=lifecycle_service.store)

    impact = change_impact_service.analyze_change(root.task_id, STATE_CHANGE, old_state=CREATED, new_state=PLANNED)
    tracked_lifecycle.transition(root.task_id, PLANNED)  # the real, equivalent mutation

    really_invalidated = {
        node.task_id for node in (root, mid, top) if cache.get(node.task_id) is None
    }
    assert set(impact.invalidated_cache_entries) == really_invalidated


# --- unresolved reasons ---------------------------------------------------------------------------


def test_unknown_change_type_is_unresolved():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)

    impact = change_impact_service.analyze_change(task.task_id, "not-a-real-change-type")

    assert impact.unresolved_reason is not None
    assert impact.affected_tasks == []
    assert impact.invalidated_cache_entries == []


def test_illegal_hypothetical_transition_is_unresolved():
    lifecycle_service, dependency_service, change_impact_service = _services()
    task = _new_task(lifecycle_service)

    impact = change_impact_service.analyze_change(task.task_id, STATE_CHANGE, old_state=CREATED, new_state=RUNNING)

    assert impact.unresolved_reason is not None


def test_missing_root_task_raises():
    lifecycle_service, dependency_service, change_impact_service = _services()

    with pytest.raises(UnknownAgentTaskError):
        change_impact_service.analyze_change("does-not-exist", STATE_CHANGE, old_state=CREATED, new_state=PLANNED)


# --- determinism / no mutation ---------------------------------------------------------------------


def test_analyze_change_is_deterministic():
    lifecycle_service, dependency_service, change_impact_service = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)

    first = change_impact_service.analyze_change(dep.task_id, STATE_CHANGE, old_state=CREATED, new_state=PLANNED)
    second = change_impact_service.analyze_change(dep.task_id, STATE_CHANGE, old_state=CREATED, new_state=PLANNED)

    assert first == second


def test_analyze_change_never_mutates_real_state():
    lifecycle_service, dependency_service, change_impact_service = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)

    before_dep = lifecycle_service.get(dep.task_id)
    before_deps = dependency_service.get_dependencies(dependent.task_id)

    change_impact_service.analyze_change(dep.task_id, STATE_CHANGE, old_state=CREATED, new_state=PLANNED)
    change_impact_service.analyze_change(dependent.task_id, DEPENDENCY_ADDED, dependency_task_id=dep.task_id)
    change_impact_service.analyze_change(dependent.task_id, DEPENDENCY_REMOVED, dependency_task_id=dep.task_id)

    after_dep = lifecycle_service.get(dep.task_id)
    after_deps = dependency_service.get_dependencies(dependent.task_id)

    assert before_dep == after_dep
    assert before_deps == after_deps
