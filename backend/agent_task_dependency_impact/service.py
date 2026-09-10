from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_lifecycle import (
    CANCELLED,
    COMPLETED,
    FAILED,
    LLMAgentTaskLifecycleService,
    UnknownAgentTaskError,
)

from .models import AgentTaskDependencyImpact

_TERMINAL_ON_ITS_OWN = frozenset({FAILED, CANCELLED})


class LLMAgentTaskDependencyImpactService:
    """Read-only downstream impact preview: if task_id changes (its
    lifecycle state moves, or it never completes), which Commit #5
    dependents could be affected or are already blocked by it right
    now.

    Not a second graph or scheduling system: every dependent edge comes
    straight from Commit #5's own LLMAgentTaskDependencyService.
    get_dependents() (Rule: "reuse the existing dependency resolver and
    lifecycle state model" / "do not duplicate dependency traversal
    logic"), and "is this dependent currently blocked" is answered
    entirely by handing that dependent's own task_id to Commit #6's own
    LLMAgentTaskDependencyResolver.resolve() and reading its result --
    never a second upstream traversal or a second cycle/taint
    computation of this service's own. This is the mirror image of
    Commit #6: that resolver looks *upstream* from one task_id (what it
    depends on); this service looks *downstream* (what depends on it),
    then reuses that same resolver, once per dependent, to judge each
    one's own current standing.

    analyze() never blocks, cancels, retries, reschedules, or otherwise
    mutates task_id or any dependent (Rule: "do not automatically
    block, cancel, retry, or reschedule tasks") -- it only classifies
    what has already actually happened, via Commit #1's own current_state
    and Commit #6's own resolve(), never anything hypothetical or
    speculative.
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        dependency_service: LLMAgentTaskDependencyService,
        dependency_resolver: LLMAgentTaskDependencyResolver,
    ):
        self._lifecycle_service = lifecycle_service
        self._dependency_service = dependency_service
        self._dependency_resolver = dependency_resolver

    def analyze(self, task_id: str) -> AgentTaskDependencyImpact:
        """Every Commit #5 dependent downstream of task_id, classified
        by its own actual Commit #1 state and Commit #6 resolution.

        Raises:
            UnknownAgentTaskError: If task_id was never created via
                Commit #1
        """
        self._lifecycle_service.get(task_id)

        direct_dependents = self._dependency_service.get_dependents(task_id)
        transitive_dependents = self._dependency_service.get_dependents(task_id, transitive=True)

        affected, blocked, completed = [], [], []
        for dependent in transitive_dependents:
            try:
                dependent_task = self._lifecycle_service.get(dependent)
            except UnknownAgentTaskError:
                # A malformed/externally-edited edge: the dependent
                # itself no longer exists. Conservatively counted as
                # both affected and blocked rather than silently
                # dropped -- nothing about it can be verified, the same
                # "never hide a structural gap" discipline Commit #6's
                # own unresolved_dependencies already applies upstream.
                affected.append(dependent)
                blocked.append(dependent)
                continue

            if dependent_task.current_state == COMPLETED:
                completed.append(dependent)
                continue

            affected.append(dependent)

            if dependent_task.current_state in _TERMINAL_ON_ITS_OWN:
                # Already terminally resolved on its own terms,
                # independent of task_id -- "blocked" (still open,
                # still waiting) does not describe it.
                continue

            resolution = self._dependency_resolver.resolve(dependent)
            if (
                resolution.ready_dependencies
                or resolution.pending_dependencies
                or resolution.failed_dependencies
                or resolution.blocked_dependencies
                or resolution.unresolved_dependencies
                or resolution.cycles
            ):
                blocked.append(dependent)

        impact_summary = (
            f"{len(direct_dependents)} direct dependent(s), {len(transitive_dependents)} transitive dependent(s); "
            f"{len(affected)} affected, {len(blocked)} blocked, {len(completed)} completed"
        )

        return AgentTaskDependencyImpact(
            task_id=task_id,
            direct_dependents=direct_dependents,
            transitive_dependents=transitive_dependents,
            affected_tasks=affected,
            blocked_tasks=blocked,
            completed_affected_tasks=completed,
            impact_summary=impact_summary,
        )
