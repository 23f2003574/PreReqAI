from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTaskDependencyResolution:
    """LLMAgentTaskDependencyResolver.resolve()'s complete, structured
    outcome for one task_id's whole transitive Commit #5 dependency
    graph -- never a bare True/False, so every reason task_id's
    prerequisites are not yet fully satisfied is reported at once
    (Rule: "do not hide cycles or missing dependencies").

    Every list holds Commit #1 task_id values, task_id itself never
    included in any of them (the same "never includes itself" convention
    Commit #5's own get_dependencies()/get_dependents() already
    establish). Each real (non-missing, non-cyclic) dependency appears in
    exactly one of ready/pending/failed/blocked, or in none of them at
    all when it is already Commit #1 COMPLETED -- the same "no bucket
    means satisfied" convention Commit #5's own AgentTaskDependencyResult
    already uses.

        ordered_dependencies: every real, non-cyclic transitive
            dependency, in one deterministic topological order
            (prerequisites before the things that depend on them) --
            Rule 2/"deterministic ordering for identical graphs".
            Excludes unresolved_dependencies (nothing to order: the
            referenced task does not exist) and cycles (a cyclic
            subgraph has no valid topological order at all).
        ready_dependencies: the dependency *frontier* -- not yet
            COMPLETED, but every one of its own direct dependencies
            already is (vacuously true for a leaf with none) -- Rule
            5/"the dependency frontier that must complete before the
            task can proceed". These are exactly the dependencies with
            nothing further standing in their own way right now.
        pending_dependencies: not yet COMPLETED, and still waiting on
            at least one of its own direct dependencies to finish first
            -- not yet part of the frontier.
        failed_dependencies: Commit #1 FAILED or CANCELLED -- terminal,
            can now never itself reach COMPLETED.
        blocked_dependencies: real, itself neither failed nor cyclic,
            but whose own transitive dependency chain includes a failed,
            unresolved, or cyclic node -- propagated unsatisfiability,
            distinct from failing on its own terms.
        unresolved_dependencies: dependency task_ids reachable in the
            graph that were never actually created via Commit #1 at all
            -- a structural gap, never silently dropped (Rule: "do not
            hide ... missing dependencies").
        cycles: every task_id (task_id itself included, when it
            participates) caught in a dependency cycle reachable from
            task_id -- Rule 4/"detect ... cyclic graphs", defensive
            against a store edited outside Commit #5 (add_dependency()
            itself already keeps the graph acyclic by construction).

    Computing this result never executes, schedules, or mutates task_id,
    any of its dependencies, or the dependency graph itself (Rule:
    "read-only" / "never execute or mutate dependency/task state").
    """

    task_id: str
    ordered_dependencies: list
    ready_dependencies: list
    pending_dependencies: list
    failed_dependencies: list
    blocked_dependencies: list
    unresolved_dependencies: list
    cycles: list
