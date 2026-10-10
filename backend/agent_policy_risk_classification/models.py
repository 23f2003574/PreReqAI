from dataclasses import dataclass

# Confidence is a different axis than Commit #1's own LEVEL_LOW/MEDIUM/
# HIGH/CRITICAL risk severity (how much evidence backed a classification,
# not how risky the action is), so it is not borrowed from that
# vocabulary -- but the repository has no existing "confidence" scale to
# reuse either, so this is deliberately the same minimal three-value
# shape the goal's own fallback ("if none exist, use a minimal low |
# medium | high ... model") already sanctions for a scale nothing in the
# repo defines yet.
CONFIDENCE_LOW = "LOW"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_LEVELS = (CONFIDENCE_LOW, CONFIDENCE_MEDIUM, CONFIDENCE_HIGH)


@dataclass(frozen=True)
class RiskClassification:
    """LLMAgentPolicyRiskClassifier.classify()'s consistent, downstream-
    consumable severity classification of one Commit #1 RiskAssessment.

    Not a second risk computation: classify() never talks to policy,
    tool, or audit collaborators itself -- every field here is derived
    solely from the RiskAssessment it was given (see Rules:
    "Classification must be derived only from the assessment").

    Deliberately carries no timestamp, the same determinism discipline
    backend.agent_policy_risk_assessment.RiskAssessment and
    backend.agent_policy_deployment_verification.VerificationResult
    already established for their own repeated-call equality.

    Attributes:
        risk_level: Commit #1's own LEVEL_LOW/LEVEL_MEDIUM/LEVEL_HIGH/
            LEVEL_CRITICAL, reused verbatim from assessment.risk_level --
            this module never re-derives or overrides it, since scoring
            an action's risk is Commit #1's own responsibility, not
            this classifier's (see Rules: "Do not duplicate policy
            evaluation")
        confidence: How complete the evidence behind risk_level was --
            CONFIDENCE_LOW/MEDIUM/HIGH, computed from which of
            assessment.provenance's own evidence entries were actually
            available (see LLMAgentPolicyRiskClassifier._confidence())
        evidence: Which of assessment.provenance's evidence sources were
            actually available, as {source_name: bool} -- the basis
            confidence was computed from, made explicit rather than
            left implicit in a single confidence label
        risk_factors: assessment.risk_factors, preserved verbatim (see
            Rules: "Preserve underlying risk factors")
        reasons: assessment.reasons, plus one classifier-added reason
            explaining the confidence level
        provenance: The complete Commit #1 RiskAssessment this
            classification was derived from, embedded verbatim (never
            re-summarized), alongside the evidence-availability
            computation confidence was based on
    """

    risk_level: str
    confidence: str
    evidence: dict
    risk_factors: dict
    reasons: list
    provenance: dict
