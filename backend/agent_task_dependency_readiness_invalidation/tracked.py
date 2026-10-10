from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService

from .service import LLMAgentTaskDependencyReadinessInvalidationService


class LLMAgentTaskLifecycleCacheInvalidatingService(LLMAgentTaskLifecycleService):
    """Commit #1's LLMAgentTaskLifecycleService, unchanged, with exactly
    one more step after transition() succeeds: reporting the change to
    this module's own LLMAgentTaskDependencyReadinessInvalidationService
    -- the same "delegate first, then report, always" shape backend.
    agent_task_state_history.tracked.
    LLMAgentTaskLifecycleHistoryTrackedService already establishes for
    Commit #2. Moved here from Commit #9's own agent_task_dependency_
    readiness_cache.tracked (which called the cache directly) now that
    the invalidation decision itself lives in its own service --
    whether anything actually needs evicting (e.g. an idempotent same-
    state no-op) is entirely on_task_state_changed()'s own call now,
    not this wrapper's.

    create() is never wrapped: a brand-new task cannot already have a
    stale cache entry.
    """

    def __init__(self, invalidation_service: LLMAgentTaskDependencyReadinessInvalidationService, store=None):
        super().__init__(store=store)
        self._invalidation_service = invalidation_service

    def transition(self, task_id: str, target_state: str, reason: str = None):
        previous_state = super().get(task_id).current_state
        task = super().transition(task_id, target_state, reason=reason)
        self._invalidation_service.on_task_state_changed(task_id, previous_state, task.current_state)
        return task


class LLMAgentTaskDependencyCacheInvalidatingService(LLMAgentTaskDependencyService):
    """Commit #5's LLMAgentTaskDependencyService, unchanged, with
    exactly one more step after add_dependency()/remove_dependency()
    succeeds: reporting the change to this module's own
    LLMAgentTaskDependencyReadinessInvalidationService -- the same
    "delegate first, then report" shape this module's own
    LLMAgentTaskLifecycleCacheInvalidatingService already establishes.
    Moved here from Commit #9's own agent_task_dependency_readiness_
    cache.tracked for the same reason.
    """

    def __init__(
        self,
        invalidation_service: LLMAgentTaskDependencyReadinessInvalidationService,
        lifecycle_service,
        store=None,
    ):
        super().__init__(lifecycle_service, store=store)
        self._invalidation_service = invalidation_service

    def add_dependency(self, task_id: str, dependency_task_id: str):
        edge = super().add_dependency(task_id, dependency_task_id)
        self._invalidation_service.on_dependency_changed(task_id, dependency_task_id)
        return edge

    def remove_dependency(self, task_id: str, dependency_task_id: str) -> None:
        super().remove_dependency(task_id, dependency_task_id)
        self._invalidation_service.on_dependency_changed(task_id, dependency_task_id)
