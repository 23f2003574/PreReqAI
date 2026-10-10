from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from backend.agent_risk_profile import LLMAgentRiskProfile, RiskProfileActionRule


@dataclass(frozen=True)
class LLMAgentRiskProfileVersion:
    """One immutable, numbered snapshot of a Commit #1 risk profile's own
    content -- name, action_rules, default_level, and its
    action_name/action_category specificity binding (Commit #2) -- at
    the moment LLMAgentRiskProfileVersionService.create_version()
    recorded it.

    Not a second versioning system: version is exactly Commit #1's own
    LLMAgentRiskProfile.version int, reused verbatim rather than a
    second, independently-maintained sequence number -- Commit #1
    already bumps it precisely when action_rules or default_level
    actually change (never for a name-only edit), so "a new version is
    created for every meaningful profile update" is Commit #1's own
    already-proven guarantee, not re-derived here. definition never
    includes status/created_at/updated_at/profile_id -- those are
    record bookkeeping, not "how actions should be assessed" -- and is
    never mutated once recorded (dataclass is frozen; the service never
    calls save() twice for the same version_id).

    provenance embeds the full before/after LLMAgentRiskProfile
    snapshots (before is None only for the very first version) plus the
    actor/reason a caller supplied, verbatim -- the same "embed full
    source objects, never re-summarize" convention every RiskAction/
    RiskProfileResolution/ResolvedRiskProfile.provenance in this whole
    risk lineage already keeps, and the closest analog to
    backend.agent_policy_history.LLMAgentPolicyChange's own before/after
    snapshot discipline for an unrelated record type.
    """

    profile_id: str
    version: int
    definition: dict
    provenance: dict
    version_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentRiskProfileVersion":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)


def profile_from_version(profile: LLMAgentRiskProfile, version: LLMAgentRiskProfileVersion) -> LLMAgentRiskProfile:
    """A purely in-memory LLMAgentRiskProfile reflecting version's own
    frozen definition applied to profile's real identity -- never
    persisted.

    Pulled out as its own pure function (Commit #6's own
    LLMAgentRiskProfileActivationService._prospective_profile(), moved
    here unchanged) so a later caller that needs to preview a specific
    historical version against a real profile's identity -- Commit #6's
    own activate() before ever mutating anything, and Commit #9's own
    impact analyzer, which needs the identical reconstruction to run
    Commit #5's compatibility check and Commit #8's simulator against a
    not-yet-activated version -- shares the exact same reconstruction
    rather than a second copy of it (see Rules: "No duplicate risk
    engine" / "reuse existing resolution/simulation/compatibility
    logic").
    """
    definition = version.definition
    return LLMAgentRiskProfile(
        scope_id=profile.scope_id,
        name=definition["name"],
        action_rules=[RiskProfileActionRule.from_dict(rule) for rule in definition["action_rules"]],
        default_level=definition["default_level"],
        status=profile.status,
        version=version.version,
        action_name=definition["action_name"],
        action_category=definition["action_category"],
        profile_id=profile.profile_id,
    )
