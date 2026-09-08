from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityExecutionPolicyResult:
    """LLMAgentCapabilityExecutionPolicy.evaluate()'s complete,
    provenance-preserving outcome for one (agent_id, capability_id,
    scope_id, context) request.

    decision is backend.agent_policy_engine's own ALLOW/DENY vocabulary,
    reused as-is; allowed is exactly `decision == ALLOW`. matched_policies
    is backend.agent_policy_decision.PolicyDecision.matched_rules,
    verbatim -- every LLMAgentPolicyDecision that actually determined the
    base policy verdict, never re-summarized. denials is the
    human-readable reason for every explicit denial that contributed to
    a DENY decision (empty when allowed), which may include a risk-layer
    denial alongside any base-policy one -- Rule: "explicit denials must
    remain denials; never silently override them" means this list only
    ever grows what would otherwise have been an ALLOW, never shrinks a
    DENY back down. warnings are advisory only (e.g. a risk profile
    flagging this action for review without denying it) and never
    affect `allowed` on their own. reasons is the full ordered narrative
    of every check performed, the same "never silently imply a decision"
    discipline every other *Result in this series already keeps.
    """

    allowed: bool
    decision: str
    matched_policies: list
    denials: list
    warnings: list
    reasons: list
