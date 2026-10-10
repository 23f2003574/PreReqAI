from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTaskDependencyReadinessPlan:
    """LLMAgentTaskDependencyReadinessService.build_plan()'s complete,
    deterministic, read-only readiness plan for task_id's Commit #6
    dependency resolution -- an actionable view of the same resolution,
    never a second graph or a second traversal.

    Every list holds Commit #1 task_id values, task_id itself never
    included (the same convention every dependency-graph result in this
    series already keeps).

        execution_order: task_id's *entire* transitive dependency graph
            (Commit #6's own ordered_dependencies, reused verbatim),
            already Completed dependencies included -- the full picture
            of how the graph resolves, regardless of current progress.
        required_tasks: the subset of execution_order not yet Commit #1
            COMPLETED, in the same topological order -- exactly what
            still needs to happen, in the order it needs to happen in
            (Rule 2/3: "a deterministic topological order for required
            tasks" / "the next dependency frontier" -- the frontier is
            always required_tasks' own leading entries, since the order
            is already dependency-respecting; no separate field is
            needed to name it).
        pending_tasks: required_tasks not failed, blocked, or
            unresolved -- either already actionable now (Commit #6's
            own ready_dependencies) or still queued behind another
            pending prerequisite (Commit #6's own pending_dependencies).
            Merely waiting, nothing wrong.
        blocking_tasks: required dependencies that are themselves fine
            but whose own chain includes something broken (Commit #6's
            own blocked_dependencies) -- surfaced separately from
            failed_tasks (Rule 5), since the two causes are different
            (something broken downstream of this dependency, vs. this
            dependency itself never succeeding).
        failed_tasks: required dependencies Commit #1 FAILED or
            CANCELLED on their own terms (Commit #6's own
            failed_dependencies) -- can now never themselves reach
            COMPLETED.
        unresolved_tasks: Commit #6's own unresolved_dependencies
            (a referenced task that was never created) *and* cycles
            (a dependency cycle reachable from task_id) merged into one
            field -- Rule: "cycles/missing dependencies remain explicit
            blockers," and neither is a task whose own state could ever
            resolve this on its own, unlike every other bucket here.
        ready: exactly `not (pending_tasks or blocking_tasks or
            failed_tasks or unresolved_tasks)` -- the same "no bucket
            populated means nothing stands in the way" boolean-gate
            reasoning backend.agent_task_readiness.
            LLMAgentTaskReadinessService already uses for its own
            broader readiness verdict (Rule: "reuse Commit #4 readiness
            semantics where applicable"), applied here to dependencies
            alone. True only once every required dependency has
            actually reached COMPLETED and nothing is missing or
            cyclic (Rule 4).

    Computing this plan never schedules, executes, or mutates task_id or
    any of its dependencies (Rule: "read-only; never schedule or execute
    anything") -- its only collaborator, Commit #6's own
    LLMAgentTaskDependencyResolver.resolve(), is itself entirely
    read-only.
    """

    task_id: str
    ready: bool
    execution_order: list
    required_tasks: list
    pending_tasks: list
    blocking_tasks: list
    failed_tasks: list
    unresolved_tasks: list
