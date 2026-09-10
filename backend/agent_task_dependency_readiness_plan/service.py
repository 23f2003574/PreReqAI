from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver

from .models import AgentTaskDependencyReadinessPlan


class LLMAgentTaskDependencyReadinessService:
    """Turns Commit #6's own dependency resolution into one actionable
    readiness plan: what must still complete, in what order, and what
    currently prevents task_id from becoming executable.

    Not a second dependency graph, resolver, or scheduler: build_plan()
    calls Commit #6's own LLMAgentTaskDependencyResolver.resolve() to
    do 100% of the actual traversal, cycle detection, and lifecycle-
    state classification (Rule: "reuse Commit #6 resolution semantics" /
    "do not duplicate traversal or lifecycle logic") -- every field on
    the returned AgentTaskDependencyReadinessPlan is a direct reshaping
    of that one resolution, computed by set membership alone, never a
    second walk of the graph or a second call to Commit #1's own
    LLMAgentTaskLifecycleService.

    ready is computed the same boolean-gate way backend.
    agent_task_readiness.LLMAgentTaskReadinessService's own ready flag
    already is -- true exactly when nothing blocking was found (Rule:
    "reuse Commit #4 readiness semantics where applicable") -- but
    scoped to dependencies alone: this is a focused, dependency-only
    companion to that broader, multi-check readiness gate (which itself
    already may consume Commit #6's resolver directly for its own
    "dependencies" check), not a replacement for it and not called by
    it.
    """

    def __init__(self, dependency_resolver: LLMAgentTaskDependencyResolver):
        self._dependency_resolver = dependency_resolver

    def build_plan(self, task_id: str) -> AgentTaskDependencyReadinessPlan:
        """Resolve task_id's complete dependency graph (Commit #6) and
        reshape it into one actionable readiness plan.

        Raises:
            UnknownAgentTaskError: If task_id was never created via
                Commit #1 (propagated from resolve() unchanged)
        """
        resolution = self._dependency_resolver.resolve(task_id)

        ready_now = set(resolution.ready_dependencies)
        still_pending = set(resolution.pending_dependencies)
        failed = set(resolution.failed_dependencies)
        blocked = set(resolution.blocked_dependencies)

        not_completed = ready_now | still_pending | failed | blocked
        required_tasks = [node for node in resolution.ordered_dependencies if node in not_completed]

        pending_tasks = sorted(ready_now | still_pending)
        blocking_tasks = sorted(blocked)
        failed_tasks = sorted(failed)
        unresolved_tasks = sorted(set(resolution.unresolved_dependencies) | set(resolution.cycles))

        ready = not (pending_tasks or blocking_tasks or failed_tasks or unresolved_tasks)

        return AgentTaskDependencyReadinessPlan(
            task_id=task_id,
            ready=ready,
            execution_order=resolution.ordered_dependencies,
            required_tasks=required_tasks,
            pending_tasks=pending_tasks,
            blocking_tasks=blocking_tasks,
            failed_tasks=failed_tasks,
            unresolved_tasks=unresolved_tasks,
        )
