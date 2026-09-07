from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Two closed outcomes for one activate() call -- the same plain-string
# status vocabulary backend.agent_policy_template_deployment.DeploymentResult
# already uses for an analogous "did this call actually change anything"
# distinction. ALREADY_ACTIVE is never a failure: it is activate()'s own
# idempotent outcome when the requested version's content already
# matches what the profile is currently, live, resolving with.
ACTIVATED = "activated"
ALREADY_ACTIVE = "already_active"
STATUSES = frozenset({ACTIVATED, ALREADY_ACTIVE})


@dataclass(frozen=True)
class ActivationResult:
    """activate()'s complete, provenance-preserving outcome for one
    (profile_id, version, scope_id) call.

    requested_version is exactly the version number a caller asked to
    activate; version is the profile's own resulting, live Commit #1
    version number afterward -- these can legitimately differ: applying
    an older version's content onto a profile that has since moved on
    never rewrites that older version's own immutable definition (Rule:
    "Never mutate immutable versions"), it mints a brand new version
    number carrying that restored content forward instead (Commit #4's
    own create_version() already guarantees this). previous_version is
    the profile's own version immediately before this call. status is
    ALREADY_ACTIVE precisely when version == previous_version -- the
    requested content was already what the profile is live with, so
    nothing changed.

    provenance embeds Commit #4's own full LLMAgentRiskProfileVersion
    records (both the one requested and the one that ended up live) and
    Commit #5's own full CompatibilityResult, verbatim -- the same
    "embed full source objects, never re-summarize" convention every
    result type in this whole risk lineage already keeps -- plus
    whatever actor/reason a caller supplied.
    """

    profile_id: str
    scope_id: str
    requested_version: int
    version: int
    previous_version: int
    status: str
    provenance: dict
    activation_id: str = field(default_factory=lambda: str(uuid4()))
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["activated_at"] = self.activated_at.isoformat()
        return data
