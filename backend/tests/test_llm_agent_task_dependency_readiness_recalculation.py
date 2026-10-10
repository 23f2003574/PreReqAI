import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService, TaskDependency
from backend.agent_task_dependency_impact import LLMAgentTaskDependencyImpactService
from backend.agent_task_dependency_readiness_cache import LLMAgentTaskDependencyReadinessCache
from backend.agent_task_dependency_readiness_plan import LLMAgentTaskDependencyReadinessService
from backend.agent_task_dependency_readiness_recalculation import (
    FIRST_COMPUTED,
    NEWLY_BLOCKED,
    NEWLY_READY,
    UNCHANGED,
    AgentTaskReadinessRecalculationResult,
    LLMAgentTaskDependencyReadinessRecalculator,
)
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import (
    COMPLETED,
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
    dependency_impact_service = LLMAgentTaskDependencyImpactService(lifecycle_service, dependency_service, resolver)
    readiness_plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    recalculator = LLMAgentTaskDependencyReadinessRecalculator(dependency_impact_service, readiness_plan_service, cache)
    return lifecycle_service, dependency_service, cache, recalculator


# --- only affected tasks are recalculated -------------------------------------------------------


def test_only_affected_tasks_are_recalculated():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)
    unrelated = _new_task(lifecycle_service)

    result = recalculator.recalculate(task.task_id)

    assert isinstance(result, AgentTaskReadinessRecalculationResult)
    assert result.changed_task_id == task.task_id
    assert sorted(result.affected_tasks) == sorted([task.task_id, dependent.task_id])
    assert sorted(result.recalculated_tasks) == sorted([task.task_id, dependent.task_id])
    assert unrelated.task_id not in result.affected_tasks
    assert unrelated.task_id not in result.recalculated_tasks
    assert cache.get(unrelated.task_id) is None  # never touched


def test_missing_changed_task_raises():
    lifecycle_service, dependency_service, cache, recalculator = _services()

    with pytest.raises(UnknownAgentTaskError):
        recalculator.recalculate("does-not-exist")


# --- newly-ready task detected -----------------------------------------------------------------


def test_newly_ready_task_detected():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)
    recalculator.recalculate(dep.task_id)  # seeds the cache with the "not ready" baseline

    dependency_service.remove_dependency(dependent.task_id, dep.task_id)
    result = recalculator.recalculate(dependent.task_id)

    change_by_task = {change.task_id: change for change in result.readiness_changes}
    assert change_by_task[dependent.task_id].transition == NEWLY_READY
    assert change_by_task[dependent.task_id].previous_ready is False
    assert change_by_task[dependent.task_id].current_ready is True


def test_state_change_evicts_stale_downstream_cache_entries_via_the_fingerprint():
    # A real Commit #1 transition bumps the changed task's own updated_at
    # -- and that task_id is always part of every downstream dependent's
    # own cached-plan fingerprint (Commit #9's own staleness check), so by
    # the time recalculate() runs, Commit #9's cache has *already*
    # (correctly) evicted every affected dependent's previous entry on
    # its own, lazily, via get() -- independent of whichever tracked
    # wrapper or recalculator ever calls invalidate() explicitly. This
    # means a *state* change (unlike a dependency add/remove, which
    # touches no AgentTask.updated_at at all -- see test_newly_ready_task_
    # detected/test_newly_blocked_task_detected above, both dependency
    # changes) can never show FIRST_COMPUTED's opposite (a real previous
    # value) for a genuinely-affected downstream task: there is no
    # "before" left to compare against once the very thing that changed
    # is itself part of what made that "before" stale.
    lifecycle_service, dependency_service, cache, recalculator = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)
    recalculator.recalculate(dep.task_id)
    assert cache.get(dependent.task_id) is not None  # seeded

    lifecycle_service.transition(dep.task_id, PLANNED)
    assert cache.get(dependent.task_id) is None  # already evicted, before recalculate() ever runs

    result = recalculator.recalculate(dep.task_id)

    change_by_task = {change.task_id: change for change in result.readiness_changes}
    assert change_by_task[dependent.task_id].transition == FIRST_COMPUTED
    assert change_by_task[dependent.task_id].previous_ready is None


# --- newly-blocked task detected ----------------------------------------------------------------


def test_newly_blocked_task_detected():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    recalculator.recalculate(task.task_id)  # seeds the cache: task has no deps, ready=True

    new_prereq = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, new_prereq.task_id)
    result = recalculator.recalculate(task.task_id)

    change_by_task = {change.task_id: change for change in result.readiness_changes}
    assert change_by_task[task.task_id].transition == NEWLY_BLOCKED
    assert change_by_task[task.task_id].previous_ready is True
    assert change_by_task[task.task_id].current_ready is False


# --- unchanged task reported correctly ------------------------------------------------------------


def test_unchanged_task_reported_correctly():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    dep = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, dep.task_id)
    recalculator.recalculate(dep.task_id)  # seeds cache: dependent not ready (dep not completed)

    # An idempotent re-run with no real change in between: dep's own
    # updated_at never moved, so Commit #9's cache still holds a valid
    # (non-stale) previous entry for dependent to compare against.
    result = recalculator.recalculate(dep.task_id)

    change_by_task = {change.task_id: change for change in result.readiness_changes}
    assert change_by_task[dependent.task_id].transition == UNCHANGED
    assert change_by_task[dependent.task_id].previous_ready is False
    assert change_by_task[dependent.task_id].current_ready is False


def test_first_computed_when_nothing_was_cached_before():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)

    result = recalculator.recalculate(task.task_id)

    change_by_task = {change.task_id: change for change in result.readiness_changes}
    assert change_by_task[task.task_id].transition == FIRST_COMPUTED
    assert change_by_task[task.task_id].previous_ready is None


# --- unrelated tasks are untouched -----------------------------------------------------------------


def test_unrelated_task_graph_untouched():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    unrelated_task = _new_task(lifecycle_service)
    unrelated_dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(unrelated_task.task_id, unrelated_dep.task_id)
    recalculator.recalculate(unrelated_task.task_id)
    cached_unrelated_before = cache.get(unrelated_task.task_id)

    recalculator.recalculate(task.task_id)

    assert cache.get(unrelated_task.task_id) == cached_unrelated_before  # byte-for-byte untouched


# --- partial recalculation failure is isolated --------------------------------------------------------


def test_partial_recalculation_failure_is_isolated():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    healthy_dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(healthy_dependent.task_id, task.task_id)
    # A malformed edge referencing a dependent that was never actually
    # created -- the same defensive scenario Commit #6/#7's own tests
    # already use for "cyclic/malformed graphs handled safely".
    dependency_service.store.save(TaskDependency(task_id="ghost-dependent", dependency_task_id=task.task_id))

    result = recalculator.recalculate(task.task_id)

    assert len(result.failed_recalculations) == 1
    assert result.failed_recalculations[0].task_id == "ghost-dependent"
    assert healthy_dependent.task_id in result.recalculated_tasks
    assert task.task_id in result.recalculated_tasks
    assert "ghost-dependent" not in result.recalculated_tasks
    # the healthy tasks still got a normal readiness_changes entry
    assert any(change.task_id == healthy_dependent.task_id for change in result.readiness_changes)


# --- cache is updated only after successful recalculation ------------------------------------------------


def test_cache_updated_only_after_successful_recalculation():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    dependency_service.store.save(TaskDependency(task_id="ghost-dependent", dependency_task_id=task.task_id))

    assert cache.get("ghost-dependent") is None

    recalculator.recalculate(task.task_id)

    # the failed task_id was never cached at all -- lifecycle_service.get()
    # itself would raise for it, so there is nothing meaningful to cache.
    assert cache.get("ghost-dependent") is None
    assert cache.get(task.task_id) is not None  # the successful one was cached


def test_cache_preserves_previous_entry_when_recalculation_fails():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    healthy_dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(healthy_dependent.task_id, task.task_id)
    recalculator.recalculate(task.task_id)
    cached_before = cache.get(healthy_dependent.task_id)
    assert cached_before is not None

    # Now introduce a malformed edge that will make a *different*,
    # unrelated recalculate() call fail for a ghost task -- proving the
    # already-good healthy_dependent entry is not disturbed by an
    # unrelated failure elsewhere in the same batch.
    dependency_service.store.save(TaskDependency(task_id="ghost-dependent", dependency_task_id=task.task_id))
    recalculator.recalculate(task.task_id)

    assert cache.get(healthy_dependent.task_id) == cached_before


# --- determinism -----------------------------------------------------------------------------------------


def test_recalculate_is_deterministic():
    lifecycle_service, dependency_service, cache, recalculator = _services()
    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)

    first = recalculator.recalculate(task.task_id)
    cache.clear()
    second = recalculator.recalculate(task.task_id)

    assert first.affected_tasks == second.affected_tasks
    assert first.recalculated_tasks == second.recalculated_tasks
