from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class RiskSimulationResult:
    """simulate()'s complete, read-only preview of how one
    LLMAgentRiskProfile would classify one action_context, without ever
    activating, persisting, or mutating that profile, or executing the
    action_context.

    risk_level/matched_rule_id/reasons are exactly what Commit #1/#2's
    own resolve_level() already computed for (profile, action_context)
    -- never recomputed or reinterpreted, so simulation and a genuine
    LLMAgentRiskProfileService.resolve()/LLMAgentRiskProfileResolver.resolve()
    call can never disagree when profile is the one actually live for
    its scope (Rule: "simulation/production parity"). matched_rules
    additionally lists *every* action_rule whose match constraints held
    -- not just the one that won by list order -- so a caller can see
    when more than one rule applied to the same action, even though
    production resolution itself only ever needed the first.

    risk_factors is the real, production
    backend.agent_policy_risk_assessment.RiskAssessment.risk_factors for
    this action_context (Rule: "use the same risk logic as production
    assessment") when LLMAgentRiskProfileSimulator was given a real
    LLMAgentPolicyRiskAssessor to compose -- an open, empty dict
    otherwise, never guessed or synthesized (the same "missing evidence
    stays explicit" discipline that assessor's own docstring already
    establishes for its own optional collaborators).

    action is Commit #3(risk-thresholds)'s own resolve_action() outcome
    (ALLOW/REVIEW/DENY) for risk_level against whichever review_at/
    deny_at LLMAgentRiskProfileSimulator was configured with (or the
    same DEFAULT_REVIEW_AT/DEFAULT_DENY_AT fallback the base risk
    pipeline's own decision engine already uses when none is
    configured).

    conflicts surfaces every disagreement this simulation actually
    found, rather than silently resolving it the way production
    matching already, correctly, does: multiple matched action_rules
    with differing levels (only the first ever took effect), and/or the
    profile's own resolved level disagreeing with what the real
    production risk assessor would otherwise classify this action as.
    Detecting one here never changes risk_level itself -- resolve_level()
    has already deterministically decided that -- it only makes the
    disagreement visible (Rule: "surface rule conflicts instead of
    hiding them"), the same reporting-only relationship
    backend.agent_policy_simulation.PolicySimulationResult.conflicts
    already keeps with that class's own final_decision.

    provenance embeds the full profile (including its version) and the
    real backend.agent_policy_risk_assessment.RiskAssessment when one
    was computed, verbatim, the same "embed full source objects, never
    re-summarize" convention every result type in this whole risk
    lineage already keeps.
    """

    profile_id: str
    scope_id: str
    profile_version: int
    risk_level: str
    risk_factors: dict
    action: str
    matched_rules: list
    matched_rule_id: Optional[str]
    conflicts: list
    reasons: list
    provenance: dict
    simulation_id: str = field(default_factory=lambda: str(uuid4()))
    simulated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["simulated_at"] = self.simulated_at.isoformat()
        return data
