from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedAgentCapabilities:
    """LLMAgentCapabilityResolver.resolve()'s complete,
    provenance-preserving outcome for one (agent_id, scope_id, context)
    request.

    capabilities and excluded_capabilities are Commit #1 LLMAgentCapability
    records, verbatim -- never copied/summarized into a second shape.
    resolution_reasons maps every considered capability_id (whether
    included or excluded) to a human-readable account of why, the same
    "never silently imply a decision" discipline
    backend.agent_policy_engine.LLMAgentPolicyDecision and
    backend.agent_risk_profile.RiskProfileResolution already keep for
    their own decisions -- a capability_id absent from
    resolution_reasons was never considered at all (it was never
    registered), which is itself meaningful.

    A pure record of the resolver's own decision: it performs no
    resolution of its own.
    """

    agent_id: str
    scope_id: str
    capabilities: list
    excluded_capabilities: list
    resolution_reasons: dict
