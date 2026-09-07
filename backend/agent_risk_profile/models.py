from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_policy_risk_assessment import LEVEL_LOW, LEVELS

# Same closed ACTIVE/ARCHIVED lifecycle vocabulary backend.agent_policy_engine
# and backend.agent_policy_templates already use for a scope-level durable
# record -- reused here rather than a third status scheme.
ACTIVE = "active"
ARCHIVED = "archived"
STATUSES = frozenset({ACTIVE, ARCHIVED})


class InvalidRiskProfileActionRuleError(ValueError):
    """Raised when a RiskProfileActionRule's fields are missing, blank, or invalid."""


@dataclass(frozen=True)
class RiskProfileActionRule:
    """One immutable action-matching rule within an LLMAgentRiskProfile's
    action_rules list.

    match is a set of {field: expected} constraints checked against the
    action_context dict LLMAgentRiskProfileService.resolve() is given --
    the exact same shape backend.agent_policy_engine.LLMAgentPolicyRule.match
    and backend.llm.tool_permissions.LLMToolPermissionPolicy.conditions
    already use (expected may be a single value or a list/tuple/set of
    acceptable values); an empty match applies unconditionally to any
    action. level is the risk level this rule assigns when matched --
    one of backend.agent_policy_risk_assessment's own existing
    LEVEL_LOW/MEDIUM/HIGH/CRITICAL vocabulary, never a new severity
    scale or a re-derived numeric score: a profile configures which of
    the assessor's own existing levels applies to a class of actions, it
    never scores anything itself.

    The rule performs no matching of its own -- matching is
    LLMAgentRiskProfileService.resolve()'s job; this is a value object
    only.
    """

    rule_id: str
    match: dict = field(default_factory=dict)
    level: str = LEVEL_LOW
    reason: str = ""

    def __post_init__(self):
        if not self.rule_id or not isinstance(self.rule_id, str):
            raise InvalidRiskProfileActionRuleError("rule_id is required and must be a non-empty string")
        if not isinstance(self.match, dict):
            raise InvalidRiskProfileActionRuleError("match must be a dict")
        for key in self.match:
            if not isinstance(key, str) or not key.strip():
                raise InvalidRiskProfileActionRuleError("match keys must be non-empty strings")
        if self.level not in LEVELS:
            raise InvalidRiskProfileActionRuleError(f"level {self.level!r} is not one of {LEVELS}")
        if not isinstance(self.reason, str):
            raise InvalidRiskProfileActionRuleError("reason must be a string")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RiskProfileActionRule":
        return cls(**data)


@dataclass
class LLMAgentRiskProfile:
    """One scope's named, versioned configuration of how different agent
    actions should be assessed, expressed entirely in terms of
    backend.agent_policy_risk_assessment's own existing LEVEL_LOW/MEDIUM/
    HIGH/CRITICAL vocabulary -- never a second risk-scoring engine.

    Mirrors backend.agent_policy_engine.LLMAgentPolicy's own scope-level,
    durable-record shape (scope_id/name/status/created_at/updated_at)
    rather than a second record convention. action_rules is what this
    record adds: an ordered list of RiskProfileActionRule, matched only
    by LLMAgentRiskProfileService.resolve(), never by the record itself.
    default_level is the level assigned to any action_context that
    matches none of action_rules -- a selected profile always has a
    definite fallback, never an implicit "no opinion" that could be
    confused with "no profile configured at all" (see resolve()'s own
    None return for that latter case).

    version starts at 1 and is bumped only by
    LLMAgentRiskProfileService.update() when action_rules or
    default_level actually changes -- a name-only edit never bumps it,
    the same discipline backend.agent_policy_templates.
    LLMAgentPolicyTemplate.version already established for its own
    definition-only version bump.

    action_name/action_category (Commit #2) are this profile's own
    optional specificity binding, used by
    backend.agent_risk_profile_resolution.LLMAgentRiskProfileResolver to
    pick the most specific applicable profile for a scope -- at most one
    of the two may be set (__post_init__-free by convention with the
    rest of this mutable record; LLMAgentRiskProfileService validates
    this), and both being None marks a scope-default profile, the exact
    role a scope's single ACTIVE profile already played before Commit
    #2. This mirrors the specific-overrides-general precedence
    backend.session.execution_network_traffic_policy_service.evaluate()
    already established for an unrelated domain (an endpoint-specific
    policy always overrides a runtime-wide default) rather than
    inventing a new precedence scheme.
    """

    scope_id: str
    name: str
    action_rules: list = field(default_factory=list)
    default_level: str = LEVEL_LOW
    status: str = ACTIVE
    version: int = 1
    action_name: Optional[str] = None
    action_category: Optional[str] = None
    profile_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["action_rules"] = [
            rule.to_dict() if isinstance(rule, RiskProfileActionRule) else rule for rule in self.action_rules
        ]
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentRiskProfile":
        payload = dict(data)
        payload["action_rules"] = [
            rule if isinstance(rule, RiskProfileActionRule) else RiskProfileActionRule.from_dict(rule)
            for rule in payload.get("action_rules", [])
        ]
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class RiskProfileResolution:
    """LLMAgentRiskProfileService.resolve()'s complete, provenance-preserving
    outcome for one action_context against one scope's ACTIVE
    LLMAgentRiskProfile.

    level is the resolved risk level -- from the first matching
    action_rule, or the profile's own default_level when none match.
    matched_rule_id is None only when default_level was used. provenance
    embeds the full profile (including its version) and a copy of the
    action_context it was resolved against, verbatim, the same "embed a
    prior/source object, never re-summarize" convention
    backend.agent_policy_risk_thresholds.RiskAction.provenance already
    established.
    """

    profile_id: str
    scope_id: str
    version: int
    level: str
    matched_rule_id: Optional[str]
    reason: str
    provenance: dict


def constraints_met(match: dict, action_context: dict) -> bool:
    """Whether every {field: expected} constraint in match holds against
    action_context -- the exact same {field: expected} shape and
    matching semantics backend.agent_policy_engine.LLMAgentPolicyEvaluator.
    _constraints_met() and backend.llm.tool_permissions.
    LLMToolPermissionService._conditions_met() already use for an
    unrelated domain's own rule/policy match, mirrored locally here
    (Commit #1's own precedent) rather than imported cross-module."""
    for field_name, expected in match.items():
        if field_name not in action_context:
            return False
        actual = action_context[field_name]
        if isinstance(expected, (list, tuple, set, frozenset)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def resolve_level(profile: LLMAgentRiskProfile, action_context: dict):
    """The (level, matched_rule_id, reason) a single profile resolves
    action_context to: the first action_rule whose match constraints
    hold, in the profile's own list order, or profile.default_level
    when none match (matched_rule_id is then None).

    Pulled out as its own pure function (Commit #1's own resolve() body,
    unchanged in behavior) so Commit #2's
    backend.agent_risk_profile_resolution.LLMAgentRiskProfileResolver
    can reuse the exact same within-profile matching once it has already
    picked which profile applies via its own exact/category/default
    specificity hierarchy -- never a second copy of this matching logic
    (see Rules: "No new matching framework").
    """
    for rule in profile.action_rules:
        if constraints_met(rule.match, action_context):
            return rule.level, rule.rule_id, rule.reason or f"action_rule {rule.rule_id!r} matched"

    return (
        profile.default_level,
        None,
        f"no action_rule matched; using profile {profile.profile_id!r}'s default_level",
    )
