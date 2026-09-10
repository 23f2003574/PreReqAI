from dataclasses import dataclass, field
from typing import Optional

FIRST_COMPUTED = "first_computed"
NEWLY_READY = "newly_ready"
NEWLY_BLOCKED = "newly_blocked"
UNCHANGED = "unchanged"
TRANSITIONS = frozenset({FIRST_COMPUTED, NEWLY_READY, NEWLY_BLOCKED, UNCHANGED})


@dataclass(frozen=True)
class AgentTaskReadinessChange:
    """One task_id's readiness transition, from recalculate()'s own
    Commit #9 cache lookup (before) to its freshly recomputed Commit #8
    AgentTaskDependencyReadinessPlan (after).

    previous_ready is None when nothing was cached for task_id yet
    (Behavior 3: "compare previous cached/readiness results *where
    available*") -- transition is FIRST_COMPUTED in exactly that case,
    never mistaken for NEWLY_READY/NEWLY_BLOCKED (both require an actual
    prior verdict to compare against). Otherwise transition is
    UNCHANGED, NEWLY_READY, or NEWLY_BLOCKED depending on whether
    current_ready differs from previous_ready, and how.
    """

    task_id: str
    previous_ready: Optional[bool]
    current_ready: bool
    transition: str


@dataclass(frozen=True)
class AgentTaskRecalculationFailure:
    """One task_id recalculate() could not recompute readiness for,
    and why -- Rule: "partial failures must be reported per task."
    task_id's own previously cached entry (if any) is left completely
    untouched when this happens (Rule: "preserve cache correctness if
    recalculation fails")."""

    task_id: str
    error: str


@dataclass(frozen=True)
class AgentTaskReadinessRecalculationResult:
    """LLMAgentTaskDependencyReadinessRecalculator.recalculate()'s
    complete, deterministic outcome for one real change to
    changed_task_id.

    affected_tasks: changed_task_id itself plus every task currently
        downstream of it (Commit #7's own
        LLMAgentTaskDependencyImpactService.analyze().transitive_dependents)
        -- the complete set this call ever considers; nothing outside
        it is ever read or recomputed (Rule: "never traverse unrelated
        task graphs"). changed_task_id's own entry is included on
        purpose: a dependency change to it changes its own plan, and
        even a bare state change is still handled the same, uniform
        way Commit #9/#10's own cache invalidation already treats it
        (invalidate/recompute task_id's own entry unconditionally,
        the same "preserve correctness over cache efficiency" Commit #9
        Rule already established) -- consistent with the rest of this
        series rather than a new, narrower notion of "affected" invented
        just for this commit.
    recalculated_tasks: the subset of affected_tasks Commit #8's own
        build_plan() actually succeeded for -- equal to affected_tasks
        unless failed_recalculations is non-empty.
    readiness_changes: one AgentTaskReadinessChange per recalculated
        task (never for a failed one -- there is no "after" to report).
    failed_recalculations: one AgentTaskRecalculationFailure per
        affected task build_plan() raised for.
    summary: a short, human-readable rollup -- never a substitute for
        the structured fields themselves, the same convention every
        other *_summary field in this series already keeps.

    Computing this result performs exactly one write of its own: Commit
    #9's own cache.set() for each successfully recalculated task (Rule
    5/"update the existing readiness cache through its public
    interface") -- never a Commit #1 transition, a Commit #5 dependency
    edge, or any other lifecycle/dependency mutation (Rule: "this
    service owns recalculation only; lifecycle/dependency mutation
    remains elsewhere"), and never anything execution- or scheduling-
    shaped.
    """

    changed_task_id: str
    affected_tasks: list = field(default_factory=list)
    recalculated_tasks: list = field(default_factory=list)
    readiness_changes: list = field(default_factory=list)
    failed_recalculations: list = field(default_factory=list)
    summary: str = ""
