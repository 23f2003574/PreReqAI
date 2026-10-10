from backend.agent_policy_risk_assessment import LEVELS, RiskAssessment

from .models import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM, RiskClassification

# The two Commit #1 provenance entries that are genuinely optional
# (tool_registry/audit_service may not have been configured, or
# action_context may not have named tool_name/scope_id) -- policy_decision
# is checked separately below, since its absence means policy evaluation
# itself failed (Commit #1's own fail-closed path), a categorically
# different, more severe kind of missing evidence than an unconfigured
# optional collaborator.
_OPTIONAL_EVIDENCE_SOURCES = ("tool_status", "prior_denied_actions")


class InvalidRiskAssessmentError(ValueError):
    """Raised when classify() is given something other than a Commit #1
    RiskAssessment, or one with a corrupted risk_level."""


class LLMAgentPolicyRiskClassifier:
    """Turns one Commit #1 RiskAssessment into a consistent, downstream-
    consumable severity classification -- adding nothing Commit #1 did
    not already compute except a confidence read on how complete the
    evidence behind it was.

    Not a second risk-scoring engine: classify() never talks to
    LLMAgentPolicyEnforcement, LLMToolRegistryService, or
    LLMAgentPolicyAuditService itself, and never re-derives risk_level
    from a score -- that thresholding is Commit #1's
    LLMAgentPolicyRiskAssessor's own responsibility, reused here purely
    by reading assessment.risk_level (and assessment.risk_factors/
    reasons) as-is (see Rules: "Classification must be derived only
    from the assessment", "Do not duplicate policy evaluation").

    Supports exactly Commit #1's own LEVEL_LOW/LEVEL_MEDIUM/LEVEL_HIGH/
    LEVEL_CRITICAL vocabulary -- the repository's existing severity
    levels as of this series -- rather than inventing a second one (see
    Implement: "Support the repository's existing severity levels; if
    none exist, use a minimal low | medium | high | critical model").

    The one thing this classifier genuinely adds is `confidence`: how
    much of assessment.provenance's own evidence was actually available
    when Commit #1 computed risk_level, expressed with the same minimal
    CONFIDENCE_LOW/MEDIUM/HIGH scale (nothing in this repository already
    models "confidence", so this is the smallest new vocabulary that
    could satisfy the goal's own low/medium/high fallback). A missing
    policy_decision (Commit #1's own evaluation-failure path) always
    means LOW confidence, regardless of anything else -- an assessment
    that could not even resolve policy is never confidently classified,
    no matter how the rest of the score computed. Otherwise, confidence
    reflects how many of the two optional evidence sources
    (tool_status, prior_denied_actions) were actually configured and
    available: both -> HIGH, one -> MEDIUM, neither -> LOW.

    classify() is deterministic and side-effect free: it never mutates
    the assessment it is given, and performs no execution of any kind.
    """

    def classify(self, assessment: RiskAssessment) -> RiskClassification:
        """Classify one Commit #1 RiskAssessment.

        Raises:
            InvalidRiskAssessmentError: If assessment is not a
                RiskAssessment, or its risk_level is not one of Commit
                #1's own LEVELS
        """
        if not isinstance(assessment, RiskAssessment):
            raise InvalidRiskAssessmentError(
                f"assessment must be a RiskAssessment, got {type(assessment).__name__}"
            )

        if assessment.risk_level not in LEVELS:
            raise InvalidRiskAssessmentError(
                f"assessment.risk_level {assessment.risk_level!r} is not one of {sorted(LEVELS)}"
            )

        provenance = assessment.provenance if isinstance(assessment.provenance, dict) else {}

        evidence = {"policy_decision": provenance.get("policy_decision") is not None}
        for source in _OPTIONAL_EVIDENCE_SOURCES:
            evidence[source] = provenance.get(source) is not None

        confidence = self._confidence(evidence)

        reasons = list(assessment.reasons) + [
            f"confidence is {confidence.lower()}: available evidence = {evidence}"
        ]

        return RiskClassification(
            risk_level=assessment.risk_level,
            confidence=confidence,
            evidence=evidence,
            risk_factors=dict(assessment.risk_factors),
            reasons=reasons,
            provenance={"assessment": assessment, "evidence_availability": evidence},
        )

    @staticmethod
    def _confidence(evidence: dict) -> str:
        if not evidence["policy_decision"]:
            return CONFIDENCE_LOW

        available_optional = sum(1 for source in _OPTIONAL_EVIDENCE_SOURCES if evidence[source])
        if available_optional == len(_OPTIONAL_EVIDENCE_SOURCES):
            return CONFIDENCE_HIGH
        if available_optional == 0:
            return CONFIDENCE_LOW
        return CONFIDENCE_MEDIUM
