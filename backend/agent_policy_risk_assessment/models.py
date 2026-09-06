from dataclasses import dataclass

# Same LOW/MEDIUM/HIGH/CRITICAL vocabulary and 0-100 threshold shape
# backend.session.execution_policy_risk_score already established as
# this repository's own risk-severity model -- reused as a local,
# same-shape reimplementation rather than a cross-domain import, the
# exact precedent backend.agent_policy_resolution.LLMAgentPolicyResolver
# already set for reusing a session-layer model ("a from-scratch,
# same-shape reimplementation local to this module rather than an
# import of that session-layer service, which governs an unrelated
# domain... that this module has no business depending on"). No
# agent_policy_*/agent_strategy_*/llm.* module anywhere in this
# repository imports from backend.session directly; this keeps it that
# way while still not inventing a second, differently-shaped severity
# scale.
LEVEL_LOW = "LOW"
LEVEL_MEDIUM = "MEDIUM"
LEVEL_HIGH = "HIGH"
LEVEL_CRITICAL = "CRITICAL"
LEVELS = (LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH, LEVEL_CRITICAL)

MAX_SCORE = 100


def level_for_score(score: int) -> str:
    """The single source of truth mapping a 0-MAX_SCORE score to a level,
    identical to backend.session.execution_policy_risk_score's own
    thresholds, so this assessor's notion of LOW/MEDIUM/HIGH/CRITICAL
    never silently drifts from the repository's existing one."""

    if score >= 75:
        return LEVEL_CRITICAL
    if score >= 50:
        return LEVEL_HIGH
    if score >= 25:
        return LEVEL_MEDIUM
    return LEVEL_LOW


@dataclass(frozen=True)
class RiskAssessment:
    """LLMAgentPolicyRiskAssessor.assess()'s complete, provenance-preserving
    verdict for one agent action, computed entirely from evidence the
    repository already has on record -- no LLM call, no execution.

    Not a value object with its own validation (mirrors
    backend.agent_policy_decision.PolicyDecision and
    backend.agent_policy_engine.LLMAgentPolicyDecision, this module's own
    closest precedents for a decision/output type): every RiskAssessment
    is constructed exclusively by LLMAgentPolicyRiskAssessor.assess()
    itself, never by a caller assembling one from arbitrary data.

    Deliberately carries no timestamp, the same discipline
    backend.agent_policy_deployment_verification.VerificationResult
    already established for its own repeated-call determinism: two
    assess() calls for the same action_context against unchanged
    underlying state produce == RiskAssessment instances, not merely
    equivalent ones.

    Attributes:
        risk_level: One of this module's own LEVEL_LOW/LEVEL_MEDIUM/
            LEVEL_HIGH/LEVEL_CRITICAL (the same vocabulary and
            thresholds backend.session.execution_policy_risk_score
            already established for this repository)
        risk_factors: Which factors contributed to risk_level and by how
            much (raw counts/indicators, not pre-weighted), as an
            open-ended {factor_name: int} mapping -- a factor this
            assessment had no evidence for (an optional collaborator was
            not configured, or action_context did not name the field it
            needs) is omitted entirely rather than assumed zero, so
            "missing evidence remains explicit" holds structurally
        matched_policies: Every backend.agent_policy_engine.
            LLMAgentPolicyDecision that actually determined the current
            policy verdict -- empty when nothing matched
        matched_security_findings: Every prior
            backend.agent_policy_audit.LLMAgentPolicyDecisionAudit record
            (this scope's own already-redacted decision history) that
            contributed to risk_factors["prior_denied_actions"] -- empty
            when no audit_service was configured, or none matched
        reasons: Every reason string behind this assessment, in the order
            each piece of evidence was considered
        provenance: The full evidence this assessment was computed from
            -- the action_context it was given, the PolicyDecision (or
            evaluation-failure detail) it read, the tool status it
            checked, and the prior denied actions it counted -- so every
            field above is traceable back to exactly what produced it
    """

    risk_level: str
    risk_factors: dict
    matched_policies: list
    matched_security_findings: list
    reasons: list
    provenance: dict
