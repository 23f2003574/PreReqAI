from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

# Same closed ACTIVE/ARCHIVED lifecycle vocabulary
# backend.agent_policy_engine and backend.agent_strategy_library already
# use for a scope-level durable record -- reused here rather than a
# third status scheme. A template's own status is entirely independent
# of any LLMAgentPolicy instantiated from it: archiving a template never
# touches, and is never touched by, a policy already produced from it.
ACTIVE = "active"
ARCHIVED = "archived"
STATUSES = frozenset({ACTIVE, ARCHIVED})


@dataclass
class LLMAgentPolicyTemplate:
    """One reusable, versioned definition of a policy's name/rules shape
    -- never itself bound to a scope -- instantiated on demand into a
    completely ordinary Commit #1 LLMAgentPolicy.

    policy_definition is a plain dict with exactly two keys:
      - "name_template": str, the resulting LLMAgentPolicy.name, may
        embed "{parameter}" placeholders
      - "rules": a list of Commit #1 LLMAgentPolicyRule-shaped dicts,
        whose rule_id/match/reason fields may also embed "{parameter}"
        placeholders (effect may not: it must always be a literal ALLOW
        or DENY)

    Never contains a scope_id: LLMAgentPolicyTemplateService validates
    this before every create()/update(), since a template's entire point
    is to stay reusable across every scope, not fixed to one -- the real
    scope_id is only ever supplied at instantiate() time.

    version is a plain, service-maintained counter (not derived from any
    append-only trail the way
    backend.agent_policy_versioning.LLMAgentPolicyVersion is for an
    ordinary policy's rules) -- it starts at 1 and is bumped only when
    LLMAgentPolicyTemplateService.update() actually changes
    policy_definition, never for a name/description-only edit.
    """

    name: str
    description: str
    policy_definition: dict
    version: int = 1
    status: str = ACTIVE
    template_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyTemplate":
        payload = dict(data)
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class LLMAgentPolicyTemplateInstantiation:
    """One immutable, append-only record of a single instantiate() call --
    the only place a Commit #1 policy's template/version provenance is
    preserved, since LLMAgentPolicy itself carries no template field of
    its own and none is added to it here.

    Looked up by policy_id (LLMAgentPolicyTemplateService.provenance()),
    never by template_id alone, so provenance for one scope's policy can
    never be confused with another scope's -- scope_id here is the
    instantiated policy's own scope_id, copied verbatim from the real
    LLMAgentPolicy that instantiate() created.
    """

    template_id: str
    template_version: int
    scope_id: str
    policy_id: str
    parameters: dict
    instantiation_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyTemplateInstantiation":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
