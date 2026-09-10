import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_readiness_cache import (
    LLMAgentTaskDependencyCacheInvalidatingService,
    LLMAgentTaskDependencyReadinessCache,
    LLMAgentTaskDependencyReadinessCachedService,
    LLMAgentTaskLifecycleCacheInvalidatingService,
)
from backend.agent_task_dependency_readiness_plan import LLMAgentTaskDependencyReadinessService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService


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


class _CountingResolver(LLMAgentTaskDependencyResolver):
    """Counts real resolve() calls, so a test can prove a cache hit
    never triggers one."""

    def __init__(self, lifecycle_service, dependency_service):
        super().__init__(lifecycle_service, dependency_service)
        self.resolve_calls = 0

    def resolve(self, task_id):
        self.resolve_calls += 1
        return super().resolve(task_id)


def _integrated_services():
    """The fully-integrated flow: cache-backed build_plan(), plus
    lifecycle/dependency services that invalidate it automatically."""
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)

    resolver = _CountingResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cached_plan_service = LLMAgentTaskDependencyReadinessCachedService(plan_service, cache)

    tracked_lifecycle = LLMAgentTaskLifecycleCacheInvalidatingService(cache, store=lifecycle_service.store)
    tracked_dependency = LLMAgentTaskDependencyCacheInvalidatingService(
        cache, tracked_lifecycle, store=dependency_service.store
    )
    return tracked_lifecycle, tracked_dependency, cache, cached_plan_service, resolver


# --- cache hit returns equivalent plan / first lookup populates cache ------------------------


def test_first_lookup_populates_cache_and_hit_returns_equivalent_plan():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task = _new_task(lifecycle_service)

    assert cache.get(task.task_id) is None

    first = cached_plan_service.build_plan(task.task_id)
    assert resolver.resolve_calls == 1
    assert cache.get(task.task_id) == first

    second = cached_plan_service.build_plan(task.task_id)
    assert second == first
    assert resolver.resolve_calls == 1  # the resolver never ran a second time


# --- missing entry triggers fresh resolution ---------------------------------------------------


def test_missing_entry_triggers_fresh_resolution():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task = _new_task(lifecycle_service)

    plan = cached_plan_service.build_plan(task.task_id)

    assert resolver.resolve_calls == 1
    assert plan.task_id == task.task_id


# --- lifecycle change invalidates affected entries ----------------------------------------------


def test_lifecycle_change_invalidates_cached_entry():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    first = cached_plan_service.build_plan(task.task_id)
    assert first.ready is False
    assert resolver.resolve_calls == 1

    lifecycle_service.transition(dep.task_id, PLANNED)
    lifecycle_service.transition(dep.task_id, READY)
    lifecycle_service.transition(dep.task_id, RUNNING)
    lifecycle_service.transition(dep.task_id, COMPLETED)

    assert cache.get(task.task_id) is None  # invalidated by the dependency's own transition

    second = cached_plan_service.build_plan(task.task_id)
    assert second.ready is True
    assert resolver.resolve_calls == 2


# --- dependency change invalidates affected entries ---------------------------------------------


def test_dependency_graph_change_invalidates_cached_entry():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)

    first = cached_plan_service.build_plan(task.task_id)
    assert first.ready is True
    assert first.execution_order == []

    dependency_service.add_dependency(task.task_id, dep.task_id)

    assert cache.get(task.task_id) is None  # invalidated by add_dependency()

    second = cached_plan_service.build_plan(task.task_id)
    assert second.ready is False
    assert second.execution_order == [dep.task_id]


# --- downstream invalidation works transitively --------------------------------------------------


def test_downstream_invalidation_works_transitively():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    root = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    top = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, root.task_id)
    dependency_service.add_dependency(top.task_id, mid.task_id)

    plan_root = cached_plan_service.build_plan(root.task_id)
    plan_mid = cached_plan_service.build_plan(mid.task_id)
    plan_top = cached_plan_service.build_plan(top.task_id)
    assert cache.get(root.task_id) is not None
    assert cache.get(mid.task_id) is not None
    assert cache.get(top.task_id) is not None

    lifecycle_service.transition(root.task_id, PLANNED)  # root itself changes

    # root's own entry, plus every transitive dependent (mid, top), is gone.
    assert cache.get(root.task_id) is None
    assert cache.get(mid.task_id) is None
    assert cache.get(top.task_id) is None


def test_invalidate_dependents_does_not_evict_the_task_itself():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    root = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, root.task_id)
    cached_plan_service.build_plan(root.task_id)
    cached_plan_service.build_plan(dependent.task_id)

    cache.invalidate_dependents(root.task_id)

    assert cache.get(root.task_id) is not None  # untouched -- only invalidate() removes this one
    assert cache.get(dependent.task_id) is None


# --- stale entry is rejected (even without going through the tracked wrappers) --------------------


def test_stale_entry_is_rejected_via_fingerprint_even_without_explicit_invalidation():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)

    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    plan = plan_service.build_plan(task.task_id)
    cache.set(task.task_id, plan)
    assert cache.get(task.task_id) == plan

    # Mutate the *raw* lifecycle service directly -- bypassing the
    # cache-invalidating wrapper entirely.
    lifecycle_service.transition(dep.task_id, PLANNED)

    assert cache.get(task.task_id) is None  # the fingerprint check catches it anyway


def test_fresh_entry_is_not_considered_stale():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)

    task = _new_task(lifecycle_service)
    plan = plan_service.build_plan(task.task_id)
    cache.set(task.task_id, plan)

    assert cache.get(task.task_id) == plan


# --- clear ----------------------------------------------------------------------------------------


def test_clear_evicts_every_entry():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    cached_plan_service.build_plan(task_a.task_id)
    cached_plan_service.build_plan(task_b.task_id)

    evicted = cache.clear()

    assert evicted == 2
    assert cache.get(task_a.task_id) is None
    assert cache.get(task_b.task_id) is None


# --- cache operations do not mutate task/dependency state -----------------------------------------


def test_cache_operations_do_not_mutate_task_or_dependency_state():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    before_task = lifecycle_service.get(task.task_id)
    before_dep = lifecycle_service.get(dep.task_id)
    before_deps = dependency_service.get_dependencies(task.task_id)

    cached_plan_service.build_plan(task.task_id)
    cache.get(task.task_id)
    cache.invalidate(task.task_id)
    cache.invalidate_dependents(task.task_id)
    cache.clear()

    after_task = lifecycle_service.get(task.task_id)
    after_dep = lifecycle_service.get(dep.task_id)
    after_deps = dependency_service.get_dependencies(task.task_id)

    assert before_task == after_task
    assert before_dep == after_dep
    assert before_deps == after_deps


# --- idempotent transitions never invalidate -------------------------------------------------------


def test_repeated_same_state_transition_does_not_invalidate():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _integrated_services()
    task = _new_task(lifecycle_service)
    lifecycle_service.transition(task.task_id, PLANNED)
    cached_plan_service.build_plan(task.task_id)
    assert cache.get(task.task_id) is not None

    lifecycle_service.transition(task.task_id, PLANNED)  # no-op: already PLANNED

    assert cache.get(task.task_id) is not None
