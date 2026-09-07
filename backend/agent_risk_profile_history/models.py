from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# The kinds of meaningful change this trail records -- the same closed,
# small vocabulary shape backend.agent_policy_history.CHANGE_TYPES
# already establishes for an unrelated record (Commit #1/#5's own
# policy lifecycle plus its own exception events), mapped onto this
# series' own real lifecycle instead: Commit #1's create/update/archive
# and Commit #6's activate/deactivate. A change always belongs to
# exactly one of these, never inferred from before/after alone.
CREATED = "created"
UPDATED = "updated"
ARCHIVED = "archived"
ACTIVATED = "activated"
DEACTIVATED = "deactivated"
CHANGE_TYPES = frozenset({CREATED, UPDATED, ARCHIVED, ACTIVATED, DEACTIVATED})


@dataclass(frozen=True)
class LLMAgentRiskProfileChange:
    """One immutable, append-only snapshot of a meaningful change to a
    Commit #1 risk profile, or to which Commit #4 version is live for it
    via Commit #6's own activation service.

    before/after are full, JSON-safe snapshots
    (LLMAgentRiskProfile.to_dict(), with any secret-looking string value
    redacted) of the profile immediately before and immediately after
    this change -- never a field-level diff, the exact same convention
    backend.agent_policy_history.LLMAgentPolicyChange already keeps for
    its own before/after. before is None only for a CREATED change,
    since nothing existed beforehand. version is the profile's own live
    Commit #1 version number as of this change -- for ACTIVATED in
    particular this is the *resulting* version Commit #6's own
    ActivationResult reports (which may differ from whatever version
    number a caller originally requested, since restoring an older
    version mints a new one rather than rewriting it -- see Commit #6's
    own ActivationResult.requested_version/.version split).

    Never updated or deleted once recorded -- LLMAgentRiskProfileHistoryService.
    record_change() only ever appends a new LLMAgentRiskProfileChange,
    the same append-only discipline every comparable audit/history
    record in this repository already establishes.

    Attributes:
        scope_id: The scope this change happened within. A change is
            never consulted for, or leaks into, any other scope
        profile_id: The Commit #1 risk profile this change is about
        version: The profile's own live version number as of this
            change
        change_type: One of CHANGE_TYPES
        before: The profile's full snapshot immediately before this
            change, or None if nothing existed yet
        after: The profile's full snapshot immediately after this
            change
        actor: Who or what made the change, when known; None when not
            supplied
        reason: Why the change was made, when the caller supplied one
            (e.g. Commit #6's own activate() reason); None when not
            supplied
    """

    scope_id: str
    profile_id: str
    version: int
    change_type: str
    before: Optional[dict]
    after: Optional[dict]
    actor: Optional[str] = None
    reason: Optional[str] = None
    change_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentRiskProfileChange":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
