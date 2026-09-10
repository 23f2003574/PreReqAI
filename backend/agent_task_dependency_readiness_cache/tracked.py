from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_readiness_plan import (
    AgentTaskDependencyReadinessPlan,
    LLMAgentTaskDependencyReadinessService,
)
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService

from .cache import LLMAgentTaskDependencyReadinessCache


class LLMAgentTaskDependencyReadinessCachedService:
    """Commit #8's own LLMAgentTaskDependencyReadinessService.build_plan(),
    fronted by an LLMAgentTaskDependencyReadinessCache: an unchanged
    dependency graph returns the cached plan without Commit #6's
    resolver ever running again; anything else falls through to a real
    build_plan() call, cached for next time.

    Not a second planning service -- build_plan() here delegates every
    real computation to Commit #8's own service, completely unchanged,
    exactly once per cache miss. Callers that also mutate tasks/
    dependencies should do so through
    LLMAgentTaskLifecycleCacheInvalidatingService/
    LLMAgentTaskDependencyCacheInvalidatingService below (both share
    this same cache instance) so a stale plan is never served past a
    real change -- see this module's own cache.py docstring for exactly
    what staleness protection still holds even without them.
    """

    def __init__(
        self,
        plan_service: LLMAgentTaskDependencyReadinessService,
        cache: LLMAgentTaskDependencyReadinessCache,
    ):
        self._plan_service = plan_service
        self._cache = cache

    def build_plan(self, task_id: str) -> AgentTaskDependencyReadinessPlan:
        cached = self._cache.get(task_id)
        if cached is not None:
            return cached

        plan = self._plan_service.build_plan(task_id)
        self._cache.set(task_id, plan)
        return plan


class LLMAgentTaskLifecycleCacheInvalidatingService(LLMAgentTaskLifecycleService):
    """Commit #1's LLMAgentTaskLifecycleService, unchanged, with exactly
    one more step after transition() actually changes current_state:
    invalidating task_id's own cached readiness plan and every cached
    plan for a task currently downstream of it -- the same "delegate
    first, then record/invalidate, only on a real change" shape
    backend.agent_task_state_history.tracked.
    LLMAgentTaskLifecycleHistoryTrackedService and backend.
    agent_policy_history.tracked already establish elsewhere in this
    repository.

    create() is never wrapped: a brand-new task cannot already have a
    stale cache entry. transition()'s own idempotent same-state no-op
    (Commit #1's own convention) invalidates nothing either, the same
    "no real change, nothing to invalidate" reasoning
    LLMAgentTaskLifecycleHistoryTrackedService already applies to
    recording.
    """

    def __init__(self, cache: LLMAgentTaskDependencyReadinessCache, store=None):
        super().__init__(store=store)
        self._cache = cache

    def transition(self, task_id: str, target_state: str, reason: str = None):
        previous_state = super().get(task_id).current_state
        task = super().transition(task_id, target_state, reason=reason)
        if task.current_state != previous_state:
            self._cache.invalidate(task_id)
            self._cache.invalidate_dependents(task_id)
        return task


class LLMAgentTaskDependencyCacheInvalidatingService(LLMAgentTaskDependencyService):
    """Commit #5's LLMAgentTaskDependencyService, unchanged, with
    exactly one more step after add_dependency()/remove_dependency()
    succeeds: invalidating task_id's own cached readiness plan (its own
    graph just changed) and every cached plan for a task currently
    downstream of it (their own resolutions could now differ too) -- the
    same "delegate first, then invalidate" shape this module's own
    LLMAgentTaskLifecycleCacheInvalidatingService already establishes.

    dependency_task_id's own cached entry (if any) is never touched:
    gaining or losing a dependent never changes what dependency_task_id
    itself still needs before it is ready.
    """

    def __init__(self, cache: LLMAgentTaskDependencyReadinessCache, lifecycle_service, store=None):
        super().__init__(lifecycle_service, store=store)
        self._cache = cache

    def add_dependency(self, task_id: str, dependency_task_id: str):
        edge = super().add_dependency(task_id, dependency_task_id)
        self._cache.invalidate(task_id)
        self._cache.invalidate_dependents(task_id)
        return edge

    def remove_dependency(self, task_id: str, dependency_task_id: str) -> None:
        super().remove_dependency(task_id, dependency_task_id)
        self._cache.invalidate(task_id)
        self._cache.invalidate_dependents(task_id)
