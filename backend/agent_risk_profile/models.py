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
    """

    scope_id: str
    name: str
    action_rules: list = field(default_factory=list)
    default_level: str = LEVEL_LOW
    status: str = ACTIVE
    version: int = 1
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
