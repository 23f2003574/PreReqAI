from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

# Same closed ACTIVE/ARCHIVED lifecycle vocabulary
# backend.agent_policy_engine, backend.agent_policy_templates, and
# backend.agent_risk_profile already use for a durable record -- reused
# here rather than a third status scheme. Archiving a capability is a
# registry-lifecycle event only; it says nothing about whether the
# capability is actually wired into any tool/permission/policy elsewhere
# in the system.
ACTIVE = "active"
ARCHIVED = "archived"
STATUSES = frozenset({ACTIVE, ARCHIVED})

DEFAULT_VERSION = "1.0.0"


@dataclass
class LLMAgentCapability:
    """One concrete capability an LLM agent may use -- a catalog entry,
    never a tool's actual input_schema/execution shape
    (backend.llm.tools.LLMToolDefinition already owns that) and never a
    permission/policy decision (backend.llm.tool_permissions and
    backend.agent_policy_engine already own that). This is purely the
    canonical, queryable inventory record: what capabilities exist, what
    they're called, what category and version they belong to, and
    whether the registry still considers them active.

    category is a free-form, non-empty classification label (e.g.
    "retrieval", "code_execution", "planning") -- mirrors
    backend.agent_risk_profile.LLMAgentRiskProfile.action_category's own
    non-empty-string-only validation (Commit #1's own precedent) rather
    than inventing a closed CATEGORIES vocabulary the registry has no
    actual logic to branch on.

    metadata is a free-form dict for whatever additional descriptive
    attributes a capability needs (e.g. required scopes, provider,
    cost hints) -- LLMAgentCapabilityRegistry never inspects its
    contents, only that it is a dict.

    version is a plain, caller-supplied string describing this
    capability's own version (e.g. semver) -- unlike
    backend.agent_policy_templates.LLMAgentPolicyTemplate.version, it is
    never auto-incremented by the registry: register()/update() preserve
    whatever version a caller sets, changing it only when a caller
    explicitly includes it in update()'s changes.
    """

    capability_id: str
    name: str
    description: str
    category: str
    version: str = DEFAULT_VERSION
    status: str = ACTIVE
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentCapability":
        payload = dict(data)
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
