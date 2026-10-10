from backend.agent_task_dependency_readiness_plan import (
    AgentTaskDependencyReadinessPlan,
    LLMAgentTaskDependencyReadinessService,
)

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
    dependencies should do so through backend.
    agent_task_dependency_readiness_invalidation.tracked's
    LLMAgentTaskLifecycleCacheInvalidatingService/
    LLMAgentTaskDependencyCacheInvalidatingService (Commit #10 -- both
    share this same cache instance, via that commit's own
    LLMAgentTaskDependencyReadinessInvalidationService) so a stale plan
    is never served past a real change -- see this module's own
    cache.py docstring for exactly what staleness protection still
    holds even without them.
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
