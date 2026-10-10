from backend.agent_policy_risk_assessment import InvalidActionContextError
from backend.agent_risk_profile import (
    ACTIVE,
    InvalidRiskProfileError,
    LLMAgentRiskProfileService,
    resolve_level,
)

from .models import TIER_ACTION_CATEGORY, TIER_EXACT_ACTION, TIER_SCOPE_DEFAULT, ResolvedRiskProfile


class LLMAgentRiskProfileResolver:
    """Resolves the most specific ACTIVE Commit #1 LLMAgentRiskProfile
    applicable to one action_context, before risk assessment runs.

    Not a second policy-resolution framework, and not a new matching
    scheme: profile lookup is entirely
    LLMAgentRiskProfileService.list(scope_id, status=ACTIVE) (so
    ARCHIVED profiles are excluded exactly the way
    backend.agent_policy_resolution.LLMAgentPolicyResolver already
    excludes ARCHIVED policies from its own resolve()), and once a
    profile is selected its own action_rules are matched via Commit #1's
    own resolve_level() -- the exact same {field: expected}
    matching/default_level-fallback this repository already uses,
    never a duplicate copy of it.

    The specificity hierarchy itself -- an exact-action-bound profile
    outranks an action-category-bound one, which outranks a
    scope-default one -- mirrors
    backend.session.execution_network_traffic_policy_service.evaluate()'s
    own "an endpoint-specific policy always overrides a runtime-wide
    default" precedence (this repository's existing specificity
    hierarchy), applied to LLMAgentRiskProfile.action_name/
    action_category (Commit #2's own additive fields on the profile
    record) instead of an endpoint id. Because
    LLMAgentRiskProfileService.create() already enforces at most one
    ACTIVE profile per (scope_id, specificity key), at most one profile
    can ever match a given tier for a given scope -- resolution is
    deterministic by construction, with no recency tie-break needed.

    resolve() is read-only: it never mutates a profile, never persists
    anything, and never calls an LLM. It returns None -- never a
    fabricated tier or level -- when scope_id has no ACTIVE profile at
    any tier, so a caller's existing risk defaults (the assessor's own
    scoring, and the threshold service's own review_at/deny_at) remain
    entirely unchanged in that case, exactly as Commit #1's own
    resolve() already guarantees for the scope-default tier alone.
    """

    def __init__(self, profile_service: LLMAgentRiskProfileService):
        self._profile_service = profile_service

    def resolve(self, scope_id: str, action_context: dict):
        """Resolve action_context against scope_id's most specific
        applicable ACTIVE risk profile.

        Checked in order: a profile whose action_name exactly equals
        action_context.get("tool_name"); failing that, a profile whose
        action_category exactly equals action_context.get("category");
        failing that, the scope's own scope-default profile (both
        action_name and action_category None). Returns None when none
        of the three tiers has an applicable ACTIVE profile.

        Raises:
            InvalidRiskProfileError: If scope_id is missing
            InvalidActionContextError: If action_context is not a dict
        """
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskProfileError("scope_id is required and must identify a project/notebook/API")
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        active = self._profile_service.list(scope_id, status=ACTIVE)

        tool_name = action_context.get("tool_name")
        exact = [profile for profile in active if profile.action_name is not None and profile.action_name == tool_name]
        if exact:
            return self._resolved(
                exact[0], TIER_EXACT_ACTION, action_context,
                f"exact action match: profile bound to action_name={tool_name!r}",
            )

        category = action_context.get("category")
        category_matches = [
            profile
            for profile in active
            if profile.action_category is not None and profile.action_category == category
        ]
        if category is not None and category_matches:
            return self._resolved(
                category_matches[0], TIER_ACTION_CATEGORY, action_context,
                f"action category match: profile bound to action_category={category!r}",
            )

        defaults = [profile for profile in active if profile.action_name is None and profile.action_category is None]
        if defaults:
            return self._resolved(
                defaults[0], TIER_SCOPE_DEFAULT, action_context,
                f"scope default: no exact-action or action-category profile applied to scope {scope_id!r}",
            )

        return None

    @staticmethod
    def _resolved(profile, tier, action_context, tier_reason) -> ResolvedRiskProfile:
        level, matched_rule_id, rule_reason = resolve_level(profile, action_context)
        return ResolvedRiskProfile(
            profile=profile,
            profile_id=profile.profile_id,
            scope_id=profile.scope_id,
            version=profile.version,
            tier=tier,
            level=level,
            matched_rule_id=matched_rule_id,
            reason=f"{tier_reason}; {rule_reason}",
            provenance={"profile": profile, "action_context": dict(action_context), "tier": tier},
        )
