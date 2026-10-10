from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class RiskProfileImpactResult:
    """analyze()'s complete, deterministic, read-only preview of what
    activating or changing profile_id's version `version` for
    target_scope could affect.

    Every *_affected list is grounded in an actual, already-existing
    repository relationship -- never fabricated -- and stays empty when
    the repository has no such relationship to report (Rule: "If the
    repository has no existing relationship for a category, do not
    fabricate one -- leave that category empty"):

      - affected_actions: the concrete tool_name values either the
        profile's current action_rules or the target version's own
        action_rules actually reference, cross-checked against a real
        backend.llm.tools.LLMToolRegistryService when one is configured
      - affected_capabilities: the action-matching fields (e.g.
        "tool_name", "subject") the target version's own action_rules
        actually depend on -- Commit #5's own compatibility
        introspection, reused verbatim
      - affected_policies: the policy_ids of every real, already
        ACTIVE backend.agent_policy_engine.LLMAgentPolicy governing this
        same scope, when a policy_service is configured
      - affected_scopes: always exactly [target_scope] -- this
        architecture gives a risk profile no cross-scope reference of
        its own (Commit #1's own scope isolation), so nothing more can
        ever be genuinely affected

    risk_level_changes lists only the actions (by tool_name, or None for
    the default_level path with no more specific rule) whose resolved
    level under the profile's *current* state and the *target version*
    genuinely differ -- computed via Commit #1/#2's own resolve_level(),
    never a second scoring pass (Rule: "Detect when changing a rule
    alters the resulting risk level for an action").

    blocking_conflicts is exactly Commit #5's own
    LLMAgentRiskProfileCompatibility.check() reasons when the target
    version is not compatible with target_scope -- the same check
    Commit #6's own activate() already runs before ever mutating
    anything, reused here to answer "would activation actually be
    blocked" without ever calling activate() itself. warnings is every
    non-blocking backend.agent_risk_profile_simulation conflict entry
    Commit #8's own simulator surfaced while previewing each affected
    action against the target version -- conflicting matched rules, or
    the target version disagreeing with a configured production risk
    assessor -- distinct from blocking_conflicts because neither of
    these ever prevents activation on its own (Rule: "Distinguish
    blocking conflicts from non-blocking warnings").

    impact_summary is a short, human-readable rollup of the counts
    above -- never a substitute for the structured fields themselves.

    provenance embeds the full profile, the target
    LLMAgentRiskProfileVersion, and the full CompatibilityResult,
    verbatim, the same "embed full source objects, never re-summarize"
    convention every result type in this whole risk lineage already
    keeps.

    Zero side effects: analyze() never mutates, persists, activates, or
    deploys anything, and the same (profile_id, version, target_scope)
    against unchanged underlying state always produces an == result
    (Rules: "Results must be deterministic and explainable" / "No
    mutations, activation, deployment, or side effects").
    """

    profile_id: str
    version: int
    target_scope: str
    affected_actions: list
    affected_capabilities: list
    affected_policies: list
    affected_scopes: list
    risk_level_changes: list
    blocking_conflicts: list
    warnings: list
    impact_summary: str
    provenance: dict
    analysis_id: str = field(default_factory=lambda: str(uuid4()))
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["analyzed_at"] = self.analyzed_at.isoformat()
        return data
