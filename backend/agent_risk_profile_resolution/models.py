from dataclasses import dataclass
from typing import Optional

from backend.agent_risk_profile import LLMAgentRiskProfile

# The specificity hierarchy, most specific first -- the exact order
# LLMAgentRiskProfileResolver.resolve() checks tiers in. Mirrors
# backend.session.execution_network_traffic_policy_service.evaluate()'s
# own "an endpoint-specific policy always overrides a runtime-wide
# default" precedence, generalized to a third, intermediate tier this
# module's own goal names explicitly.
TIER_EXACT_ACTION = "exact_action"
TIER_ACTION_CATEGORY = "action_category"
TIER_SCOPE_DEFAULT = "scope_default"
TIERS = (TIER_EXACT_ACTION, TIER_ACTION_CATEGORY, TIER_SCOPE_DEFAULT)


@dataclass(frozen=True)
class ResolvedRiskProfile:
    """LLMAgentRiskProfileResolver.resolve()'s complete,
    provenance-preserving outcome: which of a scope's ACTIVE
    LLMAgentRiskProfile records applies to one action_context, at which
    specificity tier, and the level that profile's own action_rules (or
    default_level) resolves to for it.

    profile embeds the full, real LLMAgentRiskProfile that was selected
    (never a summarized copy), the same "embed a prior/source object
    verbatim" convention backend.agent_policy_risk_thresholds.RiskAction
    and backend.agent_risk_profile.RiskProfileResolution already
    established. tier names exactly which rung of the exact-action ->
    action-category -> scope-default hierarchy was selected, so a
    caller (or a test) never has to re-derive it from profile fields.
    matched_rule_id is the profile's own matched action_rule, or None
    when its default_level applied -- identical meaning to
    backend.agent_risk_profile.RiskProfileResolution.matched_rule_id.
    """

    profile: LLMAgentRiskProfile
    profile_id: str
    scope_id: str
    version: int
    tier: str
    level: str
    matched_rule_id: Optional[str]
    reason: str
    provenance: dict
