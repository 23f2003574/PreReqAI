from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Record lifecycle, the same closed ACTIVE/ARCHIVED vocabulary
# backend.agent_strategy_library already established for a scope-level
# durable record -- reused here rather than a third status scheme.
ACTIVE = "active"
ARCHIVED = "archived"
STATUSES = frozenset({ACTIVE, ARCHIVED})

# Rule/decision effect vocabulary, the same all-caps shape
# backend.llm.sensitive_data_policy.ACTIONS and
# backend.llm.tool_permissions.DECISIONS already use for a policy's own
# outcome -- kept deliberately separate from the ACTIVE/ARCHIVED
# record-lifecycle status above (a policy can be record-ACTIVE while its
# rules still ALLOW or DENY any given action).
ALLOW = "ALLOW"
DENY = "DENY"
EFFECTS = frozenset({ALLOW, DENY})


class InvalidPolicyRuleError(ValueError):
    """Raised when an LLMAgentPolicyRule's fields are missing, blank, or invalid."""


@dataclass(frozen=True)
class LLMAgentPolicyRule:
    """One immutable allow/deny rule within an LLMAgentPolicy's rules list.

    match is a set of {field: expected} constraints checked against the
    action/context dict LLMAgentPolicyEvaluator.evaluate() is given --
    the same shape
    backend.llm.tool_permissions.LLMToolPermissionPolicy.conditions
    already uses (expected may be a single value or a list/tuple of
    acceptable values); an empty match applies unconditionally to any
    action. The rule performs no evaluation of its own -- matching and
    conflict resolution is LLMAgentPolicyEvaluator's job, this is a value
    object only.
    """

    rule_id: str
    effect: str
    match: dict = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self):
        if not self.rule_id or not isinstance(self.rule_id, str):
            raise InvalidPolicyRuleError("rule_id is required and must be a non-empty string")
        if self.effect not in EFFECTS:
            raise InvalidPolicyRuleError(f"effect {self.effect!r} is not one of {sorted(EFFECTS)}")
        if not isinstance(self.match, dict):
            raise InvalidPolicyRuleError("match must be a dict")
        for key in self.match:
            if not isinstance(key, str) or not key.strip():
                raise InvalidPolicyRuleError("match keys must be non-empty strings")
        if not isinstance(self.reason, str):
            raise InvalidPolicyRuleError("reason must be a string")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyRule":
        return cls(**data)


@dataclass
class LLMAgentPolicy:
    """One scope's named, ordered set of deterministic allow/deny rules
    governing agent planning/execution decisions.

    Mirrors backend.agent_strategy_library.LLMAgentStrategy's own
    scope-level, durable-record shape (scope_id/name/status/created_at/
    updated_at) rather than a second record convention -- rules is what
    this record adds: an ordered list of LLMAgentPolicyRule, evaluated
    only by LLMAgentPolicyEvaluator, never by the record itself.
    """

    scope_id: str
    name: str
    rules: list = field(default_factory=list)
    status: str = ACTIVE
    policy_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["rules"] = [
            rule.to_dict() if isinstance(rule, LLMAgentPolicyRule) else rule for rule in self.rules
        ]
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicy":
        payload = dict(data)
        payload["rules"] = [
            rule if isinstance(rule, LLMAgentPolicyRule) else LLMAgentPolicyRule.from_dict(rule)
            for rule in payload.get("rules", [])
        ]
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class LLMAgentPolicyDecision:
    """evaluate()'s complete, provenance-preserving outcome for one
    action/context against one LLMAgentPolicy.

    allowed/effect are the actual decision; policy_id and rule_id (None
    only when no rule matched, or the policy itself is ARCHIVED) name
    exactly what produced it, and reason is a human-readable account --
    the same "never silently imply a decision" discipline
    backend.agent_strategy_conflict_resolution.LLMAgentStrategyConflictDecision
    already keeps for its own decisions.
    """

    allowed: bool
    effect: str
    policy_id: str
    rule_id: Optional[str]
    reason: str
