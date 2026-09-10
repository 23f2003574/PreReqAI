from dataclasses import dataclass, field
from typing import Optional

STATE_CHANGE = "state_change"
DEPENDENCY_ADDED = "dependency_added"
DEPENDENCY_REMOVED = "dependency_removed"
CHANGE_TYPES = frozenset({STATE_CHANGE, DEPENDENCY_ADDED, DEPENDENCY_REMOVED})


@dataclass(frozen=True)
class AgentTaskDependencyChangeImpact:
    """LLMAgentTaskDependencyChangeImpactService.analyze_change()'s
    complete, deterministic explanation of exactly how one described
    task/dependency change affects existing Commit #8 readiness plans
    and what a Commit #9 cache would need to invalidate for it.

    Every list holds Commit #1 task_id values. The full candidate set
    this analysis ever considers is task_id itself plus every task
    currently downstream of it (Commit #7's own transitive_dependents)
    -- nothing outside that set is ever touched or reported (Rule:
    "keep unrelated tasks out of the result"); that candidate set is
    exactly affected_tasks | unchanged_tasks (a disjoint partition).

        affected_tasks: candidate tasks whose own Commit #8
            AgentTaskDependencyReadinessPlan genuinely differs between
            the pre-change and post-change snapshot this analysis
            computed -- never every downstream task unconditionally.
        newly_blocked_tasks: the subset of affected_tasks whose plan
            was ready pre-change and is not ready post-change.
        newly_ready_tasks: the subset of affected_tasks whose plan was
            not ready pre-change and is ready post-change. A task can be
            in affected_tasks without being in either of these two --
            its own resolution details changed (e.g. which specific
            dependency is blocking it) without its overall ready/not-
            ready verdict flipping.
        unchanged_tasks: candidate tasks whose plan is byte-for-byte
            identical pre- and post-change -- considered, but genuinely
            unaffected.
        invalidated_cache_entries: exactly the candidate set (task_id
            plus every transitive dependent) -- the same, deliberately
            conservative footprint Commit #10's own
            LLMAgentTaskDependencyReadinessInvalidationService actually
            evicts for the equivalent real change (task_id's own entry
            plus every downstream dependent, unconditionally). This is
            a superset of affected_tasks whenever unchanged_tasks is
            non-empty -- illustrating Commit #9's own "preserve
            correctness over cache efficiency" Rule directly: some
            invalidated entries would not actually have produced a
            different answer, but are evicted anyway because knowing
            that in advance, without invalidation.py's own coarse
            "downstream = affected" assumption, would require exactly
            the same pre/post computation this analysis already does.
        impact_summary: a short, human-readable rollup -- never a
            substitute for the structured fields themselves, the same
            convention backend.agent_risk_profile_impact_analysis.
            RiskProfileImpactResult.impact_summary and backend.
            agent_task_dependency_impact.AgentTaskDependencyImpact.
            impact_summary already establish elsewhere in this series.
        unresolved_reason: None for a change this analysis could
            actually evaluate; otherwise a short, human-readable reason
            it could not be (Rule: "if the requested change cannot be
            evaluated, return an explicit unresolved reason") -- every
            other list is always empty when this is set.

    Computing this result never performs the described change, and
    never invalidates anything for real (Rule: "analysis only; do not
    perform the mutation or invalidation itself") -- it only ever reads
    Commit #1/#5's current state (through read-only override views, for
    the hypothetical/"post" side of the comparison) and calls Commit
    #6/#7/#8's own already-existing resolve()/analyze()/build_plan(),
    never a second graph, resolver, or cache of its own.
    """

    task_id: str
    affected_tasks: list = field(default_factory=list)
    invalidated_cache_entries: list = field(default_factory=list)
    newly_blocked_tasks: list = field(default_factory=list)
    newly_ready_tasks: list = field(default_factory=list)
    unchanged_tasks: list = field(default_factory=list)
    impact_summary: str = ""
    unresolved_reason: Optional[str] = None
