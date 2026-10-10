from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTaskDependencyImpact:
    """LLMAgentTaskDependencyImpactService.analyze()'s complete,
    deterministic, read-only preview of which downstream Commit #5
    dependents a change to task_id could affect or block.

    Every list holds Commit #1 task_id values, task_id itself never
    included (the same "never includes itself" convention Commit #5's
    own get_dependents()/get_dependencies() and Commit #6's own
    AgentTaskDependencyResolution already establish).

        direct_dependents: task_ids with a direct Commit #5 edge onto
            task_id -- exactly get_dependents(task_id).
        transitive_dependents: every task_id downstream of task_id at
            any depth -- exactly get_dependents(task_id, transitive=True),
            a superset of direct_dependents.
        affected_tasks: every transitive dependent not yet Commit #1
            COMPLETED -- still has some stake in task_id's own outcome.
            Never every downstream task unconditionally (Rule: "do not
            treat every downstream task as blocked"): a COMPLETED
            dependent already ran to completion regardless of what
            happens to task_id now, so it is reported separately (see
            completed_affected_tasks) rather than folded in here.
        blocked_tasks: the subset of affected_tasks that is *currently*
            prevented from proceeding -- computed via Commit #6's own
            LLMAgentTaskDependencyResolver.resolve() for that dependent
            (never a second traversal): any ready-but-not-yet-COMPLETED,
            pending, failed, blocked, or unresolved dependency, or any
            cycle, anywhere in the dependent's own upstream resolution.
            ready_dependencies counts here too -- Commit #6's own
            "ready" means "actionable next", not "already done", so a
            dependent with even one ready-but-incomplete prerequisite
            (task_id itself, freshly created, is exactly this case) is
            just as unable to proceed as one waiting on a pending or
            failed prerequisite. A dependent already Commit #1 FAILED/
            CANCELLED on its own terms is never included here -- it has
            already terminally resolved, independent of task_id, so
            "blocked" (still-open, still waiting) does not describe it;
            it is still counted in affected_tasks.
        completed_affected_tasks: transitive dependents already Commit
            #1 COMPLETED -- reported on their own (Rule: "completed
            downstream tasks reported separately"), never mixed into
            affected_tasks/blocked_tasks.
        impact_summary: a short, human-readable rollup of the counts
            above -- never a substitute for the structured fields
            themselves, the same convention backend.
            agent_risk_profile_impact_analysis.RiskProfileImpactResult.
            impact_summary already establishes for a comparable preview
            elsewhere in this repository.

    Computing this result never mutates, blocks, cancels, retries, or
    reschedules task_id or any dependent (Rule: "read-only" / "do not
    automatically block, cancel, retry, or reschedule tasks") -- every
    collaborator analyze() calls (Commit #1's own get(), Commit #5's own
    get_dependents(), Commit #6's own resolve()) is itself read-only.
    """

    task_id: str
    direct_dependents: list
    transitive_dependents: list
    affected_tasks: list
    blocked_tasks: list
    completed_affected_tasks: list
    impact_summary: str
