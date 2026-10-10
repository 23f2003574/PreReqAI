from datetime import datetime, timezone

from backend.agent_policy_risk_assessment import InvalidActionContextError, LLMAgentPolicyRiskAssessor
from backend.agent_policy_risk_thresholds import (
    DEFAULT_DENY_AT,
    DEFAULT_REVIEW_AT,
    LLMAgentPolicyRiskThresholdService,
    resolve_action,
)
from backend.agent_risk_profile import LLMAgentRiskProfile, constraints_met, resolve_level
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator

from .models import RiskSimulationResult


class InvalidRiskProfileSimulationError(ValueError):
    """Raised when simulate() is given something other than an
    LLMAgentRiskProfile, or a profile that fails Commit #3's own
    validator -- a broken profile configuration must be surfaced, never
    silently simulated as if it were sound."""


class LLMAgentRiskProfileSimulator:
    """Previews how one Commit #1 LLMAgentRiskProfile would classify an
    action, without ever activating, persisting, or mutating that
    profile, executing the action, or calling an LLM.

    Not a second risk engine: risk_level/matched_rule_id come from
    Commit #1/#2's own resolve_level() -- the exact same {field:
    expected} matching and default_level fallback production resolution
    already uses -- called directly against whatever profile object a
    caller hands in, never re-derived. This is deliberately a pure
    function call rather than a call through
    LLMAgentRiskProfileService.resolve()/LLMAgentRiskProfileResolver.resolve():
    those two only ever resolve a scope's current *ACTIVE* profile
    looked up by scope_id, which cannot preview a not-yet-active draft,
    an about-to-be-updated profile, or any other candidate profile a
    caller has in hand but has not (yet) made live -- exactly the
    "before activating or changing the profile" case this whole
    simulator exists for. When profile genuinely is the scope's current
    live profile, resolve_level() still produces the identical answer
    either way, since it is the one true source both paths already
    share (Rule: "simulation/production parity").

    risk_factors reuses the real, unmodified
    backend.agent_policy_risk_assessment.LLMAgentPolicyRiskAssessor
    (Rule: "use the same risk logic as production assessment") when one
    is configured -- an optional collaborator, since assembling it
    requires a full policy enforcement pipeline a caller may not always
    have handy just to preview a profile's own configured levels; when
    omitted, risk_factors stays an empty dict rather than a guessed one,
    the same "missing evidence stays explicit" discipline that
    assessor's own docstring already establishes for its own optional
    tool_registry/audit_service. Composing it here also enables this
    class's own conflict-surfacing: a profile's resolved level
    disagreeing with what real production assessment would otherwise
    conclude is exactly the kind of disagreement Rule "surface rule
    conflicts instead of hiding them" wants visible.

    action reuses Commit #3(risk-thresholds)'s own resolve_action() --
    against an explicitly configured LLMAgentPolicyRiskThresholdService,
    or, when none is configured, the exact same DEFAULT_REVIEW_AT/
    DEFAULT_DENY_AT fallback the base risk pipeline's own decision
    engine already uses for an unconfigured scope.

    Zero execution or persistence side effects, by construction: this
    class never holds a reference to a tool orchestrator, a
    step-execution service, or any profile/version/activation store, so
    there is nothing here that could execute an action, or activate,
    version, or otherwise persist anything, even by mistake.
    Deterministic for identical inputs against unchanged underlying
    state, for the same reason every collaborator it composes already
    is.
    """

    def __init__(
        self,
        threshold_service: LLMAgentPolicyRiskThresholdService = None,
        assessor: LLMAgentPolicyRiskAssessor = None,
        validator: LLMAgentRiskProfileValidator = None,
    ):
        self._threshold_service = threshold_service
        self._assessor = assessor
        self._validator = validator if validator is not None else LLMAgentRiskProfileValidator()

    def simulate(self, profile, action_context: dict) -> RiskSimulationResult:
        """Preview how profile would classify action_context.

        Raises:
            InvalidRiskProfileSimulationError: If profile is not an
                LLMAgentRiskProfile, or fails Commit #3's own validator
            InvalidActionContextError: If action_context is not a dict
        """
        if not isinstance(profile, LLMAgentRiskProfile):
            raise InvalidRiskProfileSimulationError(
                f"profile must be an LLMAgentRiskProfile, got {type(profile).__name__}"
            )
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        validation_result = self._validator.validate(profile)
        if not validation_result.is_valid:
            raise InvalidRiskProfileSimulationError(
                f"profile {profile.profile_id!r} is invalid and cannot be simulated: "
                f"{[issue.to_dict() for issue in validation_result.issues]}"
            )

        matched_rules = [rule for rule in profile.action_rules if constraints_met(rule.match, action_context)]
        risk_level, matched_rule_id, resolution_reason = resolve_level(profile, action_context)

        reasons = [resolution_reason]
        conflicts = []

        distinct_levels = {rule.level for rule in matched_rules}
        if len(distinct_levels) > 1:
            conflicts.append(
                {
                    "type": "conflicting_action_rules",
                    "matched_rule_ids": [rule.rule_id for rule in matched_rules],
                    "levels": sorted(distinct_levels),
                    "resolved_rule_id": matched_rule_id,
                }
            )
            reasons.append(
                f"{len(matched_rules)} action_rules matched with differing levels {sorted(distinct_levels)}; "
                f"rule {matched_rule_id!r} took effect by list order"
            )

        assessment = None
        risk_factors = {}
        if self._assessor is not None:
            assessment = self._assessor.assess(action_context)
            risk_factors = dict(assessment.risk_factors)
            if assessment.risk_level != risk_level:
                conflicts.append(
                    {
                        "type": "profile_assessment_disagreement",
                        "profile_level": risk_level,
                        "assessment_level": assessment.risk_level,
                    }
                )
                reasons.append(
                    f"profile resolves to {risk_level!r} but the production risk assessor would classify "
                    f"this action as {assessment.risk_level!r}"
                )

        if self._threshold_service is not None:
            thresholds = self._threshold_service.get(profile.scope_id)
            review_at, deny_at = thresholds.review_at, thresholds.deny_at
        else:
            review_at, deny_at = DEFAULT_REVIEW_AT, DEFAULT_DENY_AT

        action = resolve_action(risk_level, review_at, deny_at)

        return RiskSimulationResult(
            profile_id=profile.profile_id,
            scope_id=profile.scope_id,
            profile_version=profile.version,
            risk_level=risk_level,
            risk_factors=risk_factors,
            action=action,
            matched_rules=[rule.rule_id for rule in matched_rules],
            matched_rule_id=matched_rule_id,
            conflicts=conflicts,
            reasons=reasons,
            provenance={
                "profile": profile,
                "action_context": dict(action_context),
                "review_at": review_at,
                "deny_at": deny_at,
                "assessment": assessment,
            },
            simulated_at=datetime.now(timezone.utc),
        )
