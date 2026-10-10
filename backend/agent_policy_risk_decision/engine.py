from backend.agent_policy_engine import DENY
from backend.agent_policy_risk_assessment import LEVELS, InvalidActionContextError
from backend.agent_policy_risk_classification import RiskClassification
from backend.agent_policy_risk_thresholds import (
    DEFAULT_DENY_AT,
    DEFAULT_REVIEW_AT,
    InvalidRiskClassificationError,
    InvalidRiskThresholdsError,
    RiskThresholds,
    resolve_action,
)

from .models import RiskDecision


class LLMAgentPolicyRiskDecisionEngine:
    """Converts one Commit #2 RiskClassification and one scope's Commit
    #3 RiskThresholds into a single, actionable pre-execution RiskDecision
    -- the composition root this series has been building toward, but
    still not the real execution boundary itself: decide() only reads,
    it never runs the action_context it is given.

    Not a second policy or threshold engine: decide() never talks to
    LLMAgentPolicyEnforcement, LLMToolRegistryService, or
    LLMAgentPolicyAuditService (Commit #1's own collaborators) and never
    re-implements Commit #3's own review_at/deny_at comparison -- it
    calls Commit #3's own resolve_action() function directly (see Rules:
    "No duplicate policy evaluation" / "Apply configured thresholds
    deterministically").

    thresholds is optional: when a caller has none for this scope (e.g.
    LLMAgentPolicyRiskThresholdService was never asked to resolve one),
    decide() falls back to Commit #3's own DEFAULT_REVIEW_AT/
    DEFAULT_DENY_AT (HIGH -> REVIEW, CRITICAL -> DENY) for the
    comparison -- the exact same default RiskThresholds' own
    module-level constants already express -- rather than raising or
    guessing a different default. provenance still records thresholds
    as None in that case (missing evidence stays explicit, never
    fabricated as if a real RiskThresholds had been given).

    Explicit policy denial always wins, and DENY is never silently
    downgraded: Commit #1 already guarantees a real policy deny scores
    risk_level=CRITICAL, and Commit #3's own resolve_action() already
    guarantees CRITICAL resolves to DENY under any valid threshold
    configuration -- so in the ordinary path this holds structurally,
    the same way Commit #3 already established. As a second,
    independent safety net at this final decision layer -- in case a
    classification's own risk_level and risk_factors ever disagree
    (e.g. a hand-built or corrupted classification) -- decide() also
    checks classification.risk_factors.get("policy_denial") directly
    and forces DENY whenever it is truthy, regardless of what
    resolve_action() returned from risk_level alone. This is a
    deliberate belt-and-suspenders check, not a sign the structural
    guarantee is doubted: it makes "deny must never be silently
    downgraded" hold even if something upstream of risk_level itself
    were ever wrong.

    decide() is read-only and side-effect free: it never mutates
    action_context, classification, or thresholds, and never executes
    the action_context it is given -- performing that execution is
    entirely a later caller's responsibility, exactly as
    LLMAgentPolicyEnforcement.enforce() itself never executes anything
    either.
    """

    def decide(
        self, action_context: dict, classification: RiskClassification, thresholds: RiskThresholds = None
    ) -> RiskDecision:
        """Decide the pre-execution action_context should be allowed,
        reviewed, or denied.

        Raises:
            InvalidActionContextError: If action_context is not a dict
            InvalidRiskClassificationError: If classification is not a
                RiskClassification, or its risk_level is not one of
                Commit #1's own LEVELS
            InvalidRiskThresholdsError: If thresholds is given and is
                not a RiskThresholds
        """
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )
        if not isinstance(classification, RiskClassification):
            raise InvalidRiskClassificationError(
                f"classification must be a RiskClassification, got {type(classification).__name__}"
            )
        if classification.risk_level not in LEVELS:
            raise InvalidRiskClassificationError(
                f"classification.risk_level {classification.risk_level!r} is not one of {LEVELS}"
            )
        if thresholds is not None and not isinstance(thresholds, RiskThresholds):
            raise InvalidRiskThresholdsError(
                f"thresholds must be a RiskThresholds or None, got {type(thresholds).__name__}"
            )

        review_at = thresholds.review_at if thresholds is not None else DEFAULT_REVIEW_AT
        deny_at = thresholds.deny_at if thresholds is not None else DEFAULT_DENY_AT
        resolved_action = resolve_action(classification.risk_level, review_at, deny_at)

        reasons = list(classification.reasons)
        reasons.append(
            f"risk level {classification.risk_level!r} resolves to {resolved_action!r} against "
            f"review_at={review_at!r}/deny_at={deny_at!r}"
        )

        explicit_denial = bool(classification.risk_factors.get("policy_denial"))
        if explicit_denial:
            decision = DENY
            if resolved_action != DENY:
                reasons.append(
                    "explicit policy denial overrides a less severe threshold-resolved action"
                )
        else:
            decision = resolved_action

        provenance = {
            "action_context": dict(action_context),
            "classification": classification,
            "thresholds": thresholds,
        }

        return RiskDecision(
            decision=decision,
            risk_level=classification.risk_level,
            reasons=reasons,
            risk_factors=dict(classification.risk_factors),
            provenance=provenance,
        )
