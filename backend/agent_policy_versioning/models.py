from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LLMAgentPolicyVersion:
    """One immutable, numbered version of a Commit #1 policy's rule set.

    Not a second history system: a version is computed entirely from
    Commit #10's own append-only LLMAgentPolicyChange trail
    (LLMAgentPolicyVersionService never keeps a version store of its
    own) -- version_id is exactly the change_id of the Commit #10 change
    this version was derived from, reused as-is rather than a second
    identifier, so a version's full provenance (scope_id, before/after,
    actor, reason) is always one LLMAgentPolicyHistoryService.get() call
    away. rules is that same change's own (already secret-redacted, per
    Commit #10's own rules) `after["rules"]` snapshot, never
    re-validated or re-redacted here.

    version is a 1-based sequence number, deterministic because it is
    nothing more than this version's position among every Commit #10
    change for policy_id whose rules actually differ from the one
    before it (see LLMAgentPolicyVersionService.list_versions()) -- the
    same append-only, immutable Commit #10 data always produces the
    same version numbers, in the same order.

    created_by is the change's own actor (who or what made it, when
    known) -- reused verbatim, never re-derived.
    """

    policy_id: str
    version: int
    rules: list
    created_at: datetime
    created_by: Optional[str]
    version_id: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data
