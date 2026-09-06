from dataclasses import dataclass


@dataclass(frozen=True)
class RiskDecision:
    """LLMAgentPolicyRiskDecisionEngine.decide()'s complete, one-shot
    pre-execution decision for one agent action, combining Commit #2's
    RiskClassification with Commit #3's configured RiskThresholds.

    Not a second decision model: decision reuses Commit #1 (base
    series)'s own ALLOW/DENY constants plus Commit #3's own REVIEW value
    verbatim -- the same ALLOW/REVIEW/DENY vocabulary
    LLMAgentPolicyRiskThresholdService.evaluate() already returns via
    RiskAction, extended here with the action_context and full decision
    trail a caller at the real execution boundary needs.

    Deliberately carries no timestamp, the same determinism discipline
    every prior result type in this series (RiskAssessment,
    RiskClassification, RiskThresholds) already established -- two
    decide() calls given the same inputs are `==`.

    Attributes:
        decision: One of Commit #1's ALLOW/Commit #3's REVIEW/Commit
            #1's DENY
        risk_level: Commit #1's own LEVEL_LOW/MEDIUM/HIGH/CRITICAL,
            reused verbatim from classification.risk_level
        reasons: classification.reasons, plus this engine's own
            threshold-resolution (and, when it applied, explicit-denial
            override) reasoning appended
        risk_factors: classification.risk_factors, preserved verbatim
        provenance: The action_context, classification, and thresholds
            (None when none were given) this decision was computed
            from, each embedded verbatim
    """

    decision: str
    risk_level: str
    reasons: list
    risk_factors: dict
    provenance: dict
