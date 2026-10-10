from backend.agent_task_dependencies import LLMAgentTaskDependencyService
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
from backend.agent_task_lifecycle import COMPLETED, CREATED, PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _new_task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _integrated_services():
    """The fully-integrated flow: cache-backed build_plan(), plus
    lifecycle/dependency services that report every real change to a
    shared LLMAgentTaskDependencyReadinessInvalidationService."""
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)

    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cached_plan_service = LLMAgentTaskDependencyReadinessCachedService(plan_service, cache)

    tracked_lifecycle = LLMAgentTaskLifecycleCacheInvalidatingService(
        invalidation_service, store=lifecycle_service.store
    )
    tracked_dependency = LLMAgentTaskDependencyCacheInvalidatingService(
        invalidation_service, tracked_lifecycle, store=dependency_service.store
    )
    return tracked_lifecycle, tracked_dependency, cache, cached_plan_service


# --- LLMAgentTaskDependencyReadinessInvalidationService in isolation --------------------------


def test_on_task_state_changed_invalidates_task_and_dependents():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)

    task = _new_task(lifecycle_service)
    dependent = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent.task_id, task.task_id)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache.set(task.task_id, plan_service.build_plan(task.task_id))
    cache.set(dependent.task_id, plan_service.build_plan(dependent.task_id))

    invalidation_service.on_task_state_changed(task.task_id, CREATED, PLANNED)

    assert cache.get(task.task_id) is None
    assert cache.get(dependent.task_id) is None


def test_on_task_state_changed_no_op_for_unchanged_state():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)

    task = _new_task(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache.set(task.task_id, plan_service.build_plan(task.task_id))

    invalidation_service.on_task_state_changed(task.task_id, CREATED, CREATED)

    assert cache.get(task.task_id) is not None  # a genuine no-op invalidates nothing


def test_on_dependency_changed_invalidates_task_and_dependents_not_the_dependency():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)

    task = _new_task(lifecycle_service)
    dependency = _new_task(lifecycle_service)
    dependent_of_task = _new_task(lifecycle_service)
    dependency_service.add_dependency(dependent_of_task.task_id, task.task_id)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache.set(task.task_id, plan_service.build_plan(task.task_id))
    cache.set(dependency.task_id, plan_service.build_plan(dependency.task_id))
    cache.set(dependent_of_task.task_id, plan_service.build_plan(dependent_of_task.task_id))

    invalidation_service.on_dependency_changed(task.task_id, dependency.task_id)

    assert cache.get(task.task_id) is None
    assert cache.get(dependent_of_task.task_id) is None
    assert cache.get(dependency.task_id) is not None  # the dependency's own entry is untouched


def test_invalidation_hooks_are_harmless_for_missing_cache_entries():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)
    task = _new_task(lifecycle_service)

    invalidation_service.on_task_state_changed(task.task_id, CREATED, PLANNED)  # nothing cached
    invalidation_service.on_dependency_changed(task.task_id, "some-other-task")  # nothing cached

    assert cache.get(task.task_id) is None


def test_repeated_invalidation_is_idempotent():
    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    cache = LLMAgentTaskDependencyReadinessCache(lifecycle_service, dependency_service)
    invalidation_service = LLMAgentTaskDependencyReadinessInvalidationService(cache)
    task = _new_task(lifecycle_service)
    resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    plan_service = LLMAgentTaskDependencyReadinessService(resolver)
    cache.set(task.task_id, plan_service.build_plan(task.task_id))

    invalidation_service.on_task_state_changed(task.task_id, CREATED, PLANNED)
    invalidation_service.on_task_state_changed(task.task_id, CREATED, PLANNED)  # repeated, safe

    assert cache.get(task.task_id) is None


# --- fully integrated flow: task state change invalidates affected entries ------------------------


def test_task_state_change_invalidates_affected_entries():
    lifecycle_service, dependency_service, cache, cached_plan_service = _integrated_services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    first = cached_plan_service.build_plan(task.task_id)
    assert first.ready is False
    assert cache.get(task.task_id) is not None

    lifecycle_service.transition(dep.task_id, PLANNED)
    lifecycle_service.transition(dep.task_id, READY)
    lifecycle_service.transition(dep.task_id, RUNNING)
    lifecycle_service.transition(dep.task_id, COMPLETED)

    assert cache.get(task.task_id) is None  # invalidated by the dependency's own transition

    second = cached_plan_service.build_plan(task.task_id)
    assert second.ready is True


# --- dependency add/remove invalidates affected entries ---------------------------------------------


def test_dependency_add_invalidates_affected_entries():
    lifecycle_service, dependency_service, cache, cached_plan_service = _integrated_services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)

    first = cached_plan_service.build_plan(task.task_id)
    assert first.ready is True

    dependency_service.add_dependency(task.task_id, dep.task_id)

    assert cache.get(task.task_id) is None

    second = cached_plan_service.build_plan(task.task_id)
    assert second.ready is False


def test_dependency_remove_invalidates_affected_entries():
    lifecycle_service, dependency_service, cache, cached_plan_service = _integrated_services()
    task = _new_task(lifecycle_service)
    dep = _new_task(lifecycle_service)
    dependency_service.add_dependency(task.task_id, dep.task_id)

    first = cached_plan_service.build_plan(task.task_id)
    assert first.ready is False

    dependency_service.remove_dependency(task.task_id, dep.task_id)

    assert cache.get(task.task_id) is None

    second = cached_plan_service.build_plan(task.task_id)
    assert second.ready is True


# --- transitive dependents are invalidated -------------------------------------------------------------


def test_transitive_dependents_are_invalidated():
    lifecycle_service, dependency_service, cache, cached_plan_service = _integrated_services()
    root = _new_task(lifecycle_service)
    mid = _new_task(lifecycle_service)
    top = _new_task(lifecycle_service)
    dependency_service.add_dependency(mid.task_id, root.task_id)
    dependency_service.add_dependency(top.task_id, mid.task_id)

    cached_plan_service.build_plan(root.task_id)
    cached_plan_service.build_plan(mid.task_id)
    cached_plan_service.build_plan(top.task_id)
    assert cache.get(root.task_id) is not None
    assert cache.get(mid.task_id) is not None
    assert cache.get(top.task_id) is not None

    lifecycle_service.transition(root.task_id, PLANNED)  # root itself changes

    assert cache.get(root.task_id) is None
    assert cache.get(mid.task_id) is None  # direct dependent
    assert cache.get(top.task_id) is None  # transitive dependent


# --- unrelated tasks remain cached -----------------------------------------------------------------------


def test_unrelated_task_graphs_remain_cached():
    lifecycle_service, dependency_service, cache, cached_plan_service = _integrated_services()
    task_a = _new_task(lifecycle_service)
    dep_a = _new_task(lifecycle_service)
    dependency_service.add_dependency(task_a.task_id, dep_a.task_id)
    task_b = _new_task(lifecycle_service)  # entirely unrelated graph

    cached_plan_service.build_plan(task_a.task_id)
    cached_plan_service.build_plan(task_b.task_id)

    lifecycle_service.transition(dep_a.task_id, PLANNED)

    assert cache.get(task_a.task_id) is None  # affected
    assert cache.get(task_b.task_id) is not None  # unrelated -- never touched


# --- repeated invalidation is safe/idempotent (through the integrated flow) --------------------------------


def test_repeated_transition_related_invalidation_is_safe():
    lifecycle_service, dependency_service, cache, cached_plan_service = _integrated_services()
    task = _new_task(lifecycle_service)
    lifecycle_service.transition(task.task_id, PLANNED)
    cached_plan_service.build_plan(task.task_id)

    # Repeating the exact same (idempotent) transition again invalidates nothing new.
    lifecycle_service.transition(task.task_id, PLANNED)

    assert cache.get(task.task_id) is not None
