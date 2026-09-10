from backend.agent_task_dependency_impact import LLMAgentTaskDependencyImpactService
from backend.agent_task_dependency_readiness_cache import LLMAgentTaskDependencyReadinessCache
from backend.agent_task_dependency_readiness_plan import LLMAgentTaskDependencyReadinessService
from backend.agent_task_lifecycle import UnknownAgentTaskError

from .models import (
    FIRST_COMPUTED,
    NEWLY_BLOCKED,
    NEWLY_READY,
    UNCHANGED,
    AgentTaskReadinessChange,
    AgentTaskReadinessRecalculationResult,
    AgentTaskRecalculationFailure,
)


class LLMAgentTaskDependencyReadinessRecalculator:
    """Recomputes Commit #8 readiness plans for exactly the tasks one
    real change to changed_task_id could affect -- never the whole
    graph, never a task outside that set, and never a second dependency
    graph, cache, or readiness engine of its own (Rule: "do not create
    another dependency graph, cache, or readiness implementation").

    Every step is a direct call into an already-existing service:
      1. "determine affected downstream tasks" -- Commit #7's own
         LLMAgentTaskDependencyImpactService.analyze(changed_task_id).
         transitive_dependents, plus changed_task_id itself.
      2. "recompute readiness only for affected tasks" -- Commit #8's
         own LLMAgentTaskDependencyReadinessService.build_plan(), called
         once per affected task, always against real, current state
         (never a hypothetical/override view -- that is Commit #11's
         own job, for a change that may not have happened yet; this
         service is for a change that already has).
      3. "compare previous cached/readiness results where available" --
         Commit #9's own LLMAgentTaskDependencyReadinessCache.get(),
         read once per affected task before recomputing it.
      5. "update the existing readiness cache through its public
         interface" -- that same cache's own set(), called only after
         build_plan() actually succeeds for that task (Rule: "cache is
         updated only after successful recalculation" / "preserve
         cache correctness if recalculation fails").

    A build_plan() failure for one affected task (Commit #6's own
    UnknownAgentTaskError -- the realistic case: a Commit #5 dependency
    edge recorded against a task_id that was never actually created,
    the same defensive "malformed graph" scenario Commit #6/#7 already
    tolerate elsewhere) is caught and reported in failed_recalculations,
    never aborting the whole batch and never touching that task's own
    cache entry -- every *other* affected task is still recalculated
    and cached normally (Rule: "partial failures must be reported per
    task").

    change_type is purely an informational label folded into summary --
    optional, and never required to be one of Commit #11's own
    STATE_CHANGE/DEPENDENCY_ADDED/DEPENDENCY_REMOVED vocabulary, since a
    full, correct recompute against real current state needs to know
    only *that* changed_task_id changed, never the specific delta (Rule:
    "instead of requiring callers to manually resolve the entire
    graph" -- the caller does not have to describe the change
    precisely either).
    """

    def __init__(
        self,
        dependency_impact_service: LLMAgentTaskDependencyImpactService,
        readiness_plan_service: LLMAgentTaskDependencyReadinessService,
        cache: LLMAgentTaskDependencyReadinessCache,
    ):
        self._dependency_impact_service = dependency_impact_service
        self._readiness_plan_service = readiness_plan_service
        self._cache = cache

    def recalculate(self, changed_task_id: str, change_type: str = None) -> AgentTaskReadinessRecalculationResult:
        """Recompute readiness for changed_task_id and every task
        currently downstream of it, refreshing Commit #9's cache for
        each one that succeeds.

        Raises:
            UnknownAgentTaskError: If changed_task_id itself was never
                created via Commit #1 (propagated from Commit #7's own
                analyze(), unchanged -- the same "a missing root task_id
                is a caller error" convention every other service in
                this series already uses)
        """
        impact = self._dependency_impact_service.analyze(changed_task_id)
        affected_tasks = sorted({changed_task_id} | set(impact.transitive_dependents))

        recalculated_tasks = []
        readiness_changes = []
        failed_recalculations = []

        for task_id in affected_tasks:
            previous_plan = self._cache.get(task_id)

            try:
                new_plan = self._readiness_plan_service.build_plan(task_id)
            except UnknownAgentTaskError as error:
                failed_recalculations.append(AgentTaskRecalculationFailure(task_id=task_id, error=str(error)))
                continue

            self._cache.set(task_id, new_plan)
            recalculated_tasks.append(task_id)
            readiness_changes.append(self._change(task_id, previous_plan, new_plan))

        summary = self._summarize(
            changed_task_id, change_type, affected_tasks, readiness_changes, failed_recalculations
        )

        return AgentTaskReadinessRecalculationResult(
            changed_task_id=changed_task_id,
            affected_tasks=affected_tasks,
            recalculated_tasks=recalculated_tasks,
            readiness_changes=readiness_changes,
            failed_recalculations=failed_recalculations,
            summary=summary,
        )

    @staticmethod
    def _change(task_id, previous_plan, new_plan) -> AgentTaskReadinessChange:
        if previous_plan is None:
            transition = FIRST_COMPUTED
            previous_ready = None
        elif previous_plan.ready == new_plan.ready:
            transition = UNCHANGED
            previous_ready = previous_plan.ready
        elif new_plan.ready:
            transition = NEWLY_READY
            previous_ready = previous_plan.ready
        else:
            transition = NEWLY_BLOCKED
            previous_ready = previous_plan.ready

        return AgentTaskReadinessChange(
            task_id=task_id, previous_ready=previous_ready, current_ready=new_plan.ready, transition=transition
        )

    @staticmethod
    def _summarize(changed_task_id, change_type, affected_tasks, readiness_changes, failed_recalculations) -> str:
        newly_ready = sum(1 for change in readiness_changes if change.transition == NEWLY_READY)
        newly_blocked = sum(1 for change in readiness_changes if change.transition == NEWLY_BLOCKED)
        unchanged = sum(1 for change in readiness_changes if change.transition == UNCHANGED)
        first_computed = sum(1 for change in readiness_changes if change.transition == FIRST_COMPUTED)

        label = f"{change_type} on " if change_type else ""
        return (
            f"{label}task {changed_task_id!r}: {len(affected_tasks)} affected, "
            f"{len(readiness_changes)} recalculated ({newly_ready} newly ready, {newly_blocked} newly blocked, "
            f"{unchanged} unchanged, {first_computed} first computed), "
            f"{len(failed_recalculations)} failed"
        )
