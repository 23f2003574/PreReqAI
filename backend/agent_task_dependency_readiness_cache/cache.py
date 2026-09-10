from typing import Optional

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_readiness_plan import AgentTaskDependencyReadinessPlan
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService, UnknownAgentTaskError

from .models import AgentTaskDependencyReadinessCacheEntry


class LLMAgentTaskDependencyReadinessCache:
    """An in-memory cache of Commit #8 AgentTaskDependencyReadinessPlan
    results, keyed by task_id -- not a new global cache framework
    (Rule): a single-purpose dict, the same shape backend.llm.
    response_cache.LLMResponseCacheService already uses for its own,
    unrelated get/set/invalidate/clear cache, adapted here to graph-
    version staleness instead of that cache's own TTL expiry.

    get() never trusts a stored entry blindly: every lookup re-checks
    the entry's own fingerprint (see AgentTaskDependencyReadinessCacheEntry)
    against every fingerprinted task's *current* Commit #1 updated_at,
    evicting and returning None the moment any of them has moved on --
    Rule: "cache must never change correctness; stale data must not be
    returned." This catches a lifecycle change anywhere in the
    previously-resolved graph even if invalidate() was never called for
    it.

    That fingerprint check alone cannot catch a purely structural
    change (a Commit #5 dependency edge added or removed touches no
    AgentTask.updated_at at all) -- invalidate()/invalidate_dependents()
    exist for exactly that, and Commit #10's own backend.
    agent_task_dependency_readiness_invalidation (its own
    LLMAgentTaskDependencyReadinessInvalidationService, called from that
    same module's own tracked LLMAgentTaskDependencyCacheInvalidatingService/
    LLMAgentTaskLifecycleCacheInvalidatingService) calls them
    automatically after every real mutation, the same "the entity
    service never records/invalidates on its own; a thin wrapper does"
    split backend.agent_task_state_history.tracked and backend.
    agent_policy_history.tracked already establish elsewhere in this
    repository. A caller that bypasses those wrappers and mutates the
    raw Commit #1/#5 services directly only gets the fingerprint's own
    (lifecycle-only) staleness protection, not immediate structural
    invalidation -- documented, not hidden.

    invalidate_dependents() reuses Commit #5's own
    LLMAgentTaskDependencyService.get_dependents(transitive=True)
    verbatim (Rule: "reuse existing dependency ... identifiers") rather
    than inferring dependents from whatever happens to already be
    cached, so it is always correct against the graph's current shape,
    never a stale one.

    Every operation here only ever reads Commit #1/#5's own state
    (get()/get_dependents()) and this cache's own dict -- nothing here
    ever creates, transitions, or otherwise mutates a task or a
    dependency edge (Rule: "no task execution or scheduling").
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        dependency_service: LLMAgentTaskDependencyService,
    ):
        self._lifecycle_service = lifecycle_service
        self._dependency_service = dependency_service
        self._entries: dict[str, AgentTaskDependencyReadinessCacheEntry] = {}

    def get(self, task_id: str) -> Optional[AgentTaskDependencyReadinessPlan]:
        """task_id's cached plan, or None if nothing is cached, or the
        cached entry is now stale (evicted as a side effect)."""
        entry = self._entries.get(task_id)
        if entry is None:
            return None

        if self._is_stale(entry):
            del self._entries[task_id]
            return None

        return entry.plan

    def set(self, task_id: str, plan: AgentTaskDependencyReadinessPlan) -> AgentTaskDependencyReadinessCacheEntry:
        """Cache plan for task_id, fingerprinting every task its own
        resolution touched (task_id itself, plus every node in
        plan.execution_order) at their current updated_at."""
        entry = AgentTaskDependencyReadinessCacheEntry(
            task_id=task_id, plan=plan, fingerprint=self._fingerprint(task_id, plan)
        )
        self._entries[task_id] = entry
        return entry

    def invalidate(self, task_id: str) -> bool:
        """Evict task_id's own cached entry, if any. Returns whether one was present."""
        return self._entries.pop(task_id, None) is not None

    def invalidate_dependents(self, task_id: str) -> int:
        """Evict every cached entry for a task_id currently downstream
        of task_id (Commit #5's own get_dependents(transitive=True)) --
        never task_id's own entry (see invalidate() for that). Returns
        how many entries were actually evicted."""
        evicted = 0
        for dependent in self._dependency_service.get_dependents(task_id, transitive=True):
            if self._entries.pop(dependent, None) is not None:
                evicted += 1
        return evicted

    def clear(self) -> int:
        """Evict every cached entry. Returns how many were evicted."""
        count = len(self._entries)
        self._entries.clear()
        return count

    def _fingerprint(self, task_id: str, plan: AgentTaskDependencyReadinessPlan) -> dict:
        nodes = {task_id, *plan.execution_order}
        return {node: self._current_updated_at(node) for node in nodes}

    def _is_stale(self, entry: AgentTaskDependencyReadinessCacheEntry) -> bool:
        return any(
            self._current_updated_at(node) != recorded_updated_at
            for node, recorded_updated_at in entry.fingerprint.items()
        )

    def _current_updated_at(self, task_id: str):
        try:
            return self._lifecycle_service.get(task_id).updated_at
        except UnknownAgentTaskError:
            return None
