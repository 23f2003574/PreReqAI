from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_readiness_cache import (
    LLMAgentTaskDependencyReadinessCache,
    LLMAgentTaskDependencyReadinessCachedService,
)
from backend.agent_task_dependency_readiness_plan import LLMAgentTaskDependencyReadinessService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _new_task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


class _CountingResolver(LLMAgentTaskDependencyResolver):
    """Counts real resolve() calls, so a test can prove a cache hit
    never triggers one."""

    def __init__(self, lifecycle_service, dependency_service):
        super().__init__(lifecycle_service, dependency_service)
        self.resolve_calls = 0

    def resolve(self, task_id):
        self.resolve_calls += 1
        return super().resolve(task_id)


def _services():
    """The plain (non-integrated) flow: a bare cache plus a cache-
    checking build_plan() wrapper. Cache population/eviction is driven
    directly in each test -- Commit #10's own
    agent_task_dependency_readiness_invalidation owns wiring this cache
    up to real lifecycle/dependency mutations automatically."""
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)

    resolver = _CountingResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cached_plan_service = LLMAgentTaskDependencyReadinessCachedService(plan_service, cache)
    return lifecycle_service, dependency_service, cache, cached_plan_service, resolver


# --- cache hit returns equivalent plan / first lookup populates cache ------------------------


def test_first_lookup_populates_cache_and_hit_returns_equivalent_plan():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
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
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
    task = _new_task(lifecycle_service)

    plan = cached_plan_service.build_plan(task.task_id)

    assert resolver.resolve_calls == 1
    assert plan.task_id == task.task_id


# --- explicit invalidate / invalidate_dependents / clear -----------------------------------------


def test_invalidate_evicts_only_the_named_entry():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    cached_plan_service.build_plan(task_a.task_id)
    cached_plan_service.build_plan(task_b.task_id)

    assert cache.invalidate(task_a.task_id) is True

    assert cache.get(task_a.task_id) is None
    assert cache.get(task_b.task_id) is not None  # unrelated entry left alone


def test_invalidate_missing_entry_is_harmless():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()

    assert cache.invalidate("does-not-exist") is False
    assert cache.invalidate("does-not-exist") is False  # idempotent, still harmless


def test_invalidate_dependents_evicts_transitively_but_not_the_task_itself():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
    root = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    top = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, root.task_id)
    dependency_service.add_dependency(top.task_id, mid.task_id)
    cached_plan_service.build_plan(root.task_id)
    cached_plan_service.build_plan(mid.task_id)
    cached_plan_service.build_plan(top.task_id)

    evicted = cache.invalidate_dependents(root.task_id)

    assert evicted == 2
    assert cache.get(root.task_id) is not None  # only invalidate() removes this one
    assert cache.get(mid.task_id) is None
    assert cache.get(top.task_id) is None


def test_clear_evicts_every_entry():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
    task_a = _new_task(lifecycle_service)
    task_b = _new_task(lifecycle_service)
    cached_plan_service.build_plan(task_a.task_id)
    cached_plan_service.build_plan(task_b.task_id)

    evicted = cache.clear()

    assert evicted == 2
    assert cache.get(task_a.task_id) is None
    assert cache.get(task_b.task_id) is None


# --- stale entry is rejected via the fingerprint, even without any explicit invalidation ----------


def test_stale_entry_is_rejected_via_fingerprint():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    plan = cached_plan_service.build_plan(task.task_id)
    assert cache.get(task.task_id) == plan

    # Change dep's own state directly -- no invalidate() call at all.
    lifecycle_service.transition(dep.task_id, PLANNED)

    assert cache.get(task.task_id) is None  # the fingerprint check catches it anyway


def test_fresh_entry_is_not_considered_stale():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
    task = _new_task(lifecycle_service)

    plan = cached_plan_service.build_plan(task.task_id)

    assert cache.get(task.task_id) == plan


# --- cache operations do not mutate task/dependency state -----------------------------------------


def test_cache_operations_do_not_mutate_task_or_dependency_state():
    lifecycle_service, dependency_service, cache, cached_plan_service, resolver = _services()
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
