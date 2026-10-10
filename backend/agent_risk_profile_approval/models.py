from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Modeled directly on backend.agent_policy_risk_approval.ApprovalRequirement's
# own REQUIRED/APPROVED/REJECTED/EXPIRED vocabulary and "terminal once
# decided" discipline -- mirrored here as a from-scratch, same-shape
# reimplementation (this series' own established precedent for reusing a
# shape across unrelated domains without a cross-module import) rather
# than reused verbatim, since that gate's own ApprovalRequirement is
# permanently keyed to one specific action_context/RiskDecision pair, an
# entirely different subject than "this profile version, for this
# scope". There is deliberately no EXPIRED here: this commit's own
# Rules carry no time-bound-window requirement the way that gate's own
# Commit #7 (expiration) did, so no expiry window is invented to fill
# one in.
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
STATUSES = frozenset({PENDING, APPROVED, REJECTED})

# get_status()'s own sentinel for "no approval has ever been requested
# for this (profile_id, version, scope_id)" -- never a real, stored
# RiskProfileApproval.status value, so STATUSES itself stays the single
# source of truth for what a persisted record may actually hold.
NOT_REQUESTED = "not_requested"

# ApprovalStatus is documentation only, the same plain-string status
# vocabulary every other closed set in this repository already uses --
# never a new Enum type.
ApprovalStatus = str


class InvalidRiskProfileApprovalError(ValueError):
    """Raised when a RiskProfileApproval's fields are missing, invalid,
    or inconsistent with its own status."""


@dataclass(frozen=True)
class RiskProfileApproval:
    """Immutable record of one approval request for one exact (profile,
    version, scope) triple -- "approval is tied to an exact profile
    version and scope" held structurally, since none of the three can
    ever be changed after construction.

    A value object only, performing no state transition of its own;
    LLMAgentRiskProfileApprovalService produces a new record (via
    dataclasses.replace) for every transition rather than mutating an
    existing one -- the same discipline
    backend.agent_policy_risk_approval.ApprovalRequirement already
    established, extended here with two separate approved_by/rejected_by
    fields (this commit's own explicit field list) rather than that
    precedent's single shared `actor`, since a caller may want to know
    *which* decision a given actor made without inspecting status too.

    provenance embeds whatever Commit #3 validation / Commit #5
    compatibility / Commit #9 impact-analysis results were actually
    available at request time, verbatim -- "approval must incorporate
    the existing validation/compatibility and impact-analysis results
    where appropriate" (Rule), not re-derived later from a stale
    profile/version lookup.

    Attributes:
        approval_id: This approval's unique identifier
        profile_id: The Commit #1 risk profile this approval is about
        version: The exact Commit #4 version number this approval
            covers
        scope_id: The scope this approval belongs to. Never consulted
            for, or leaked into, any other scope
        status: PENDING, APPROVED, or REJECTED
        requested_by: Who requested this approval
        approved_by: Who approved it -- only ever set when status is
            APPROVED
        rejected_by: Who rejected it -- only ever set when status is
            REJECTED
        reason: Why a REJECTED approval was rejected. Required for
            REJECTED, never present otherwise
        provenance: The validation/compatibility/impact-analysis
            evidence this approval was requested against
        created_at: When this approval was requested
        resolved_at: When this approval was approved or rejected, or
            None while PENDING
    """

    approval_id: str
    profile_id: str
    version: int
    scope_id: str
    status: str
    requested_by: str
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    reason: Optional[str] = None
    provenance: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def __post_init__(self):
        self._require_text(self.approval_id, "approval ID")
        self._require_text(self.profile_id, "profile ID")
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.requested_by, "requested_by")

        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise InvalidRiskProfileApprovalError("version must be a positive integer")

        if self.status not in STATUSES:
            raise InvalidRiskProfileApprovalError(f"status {self.status!r} is not one of {sorted(STATUSES)}")

        if self.status == PENDING:
            if self.approved_by is not None or self.rejected_by is not None:
                raise InvalidRiskProfileApprovalError("a PENDING approval cannot have approved_by/rejected_by")
            if self.resolved_at is not None or self.reason is not None:
                raise InvalidRiskProfileApprovalError("a PENDING approval cannot have resolved_at/reason")

        if self.status == APPROVED:
            self._require_text(self.approved_by, "approved_by")
            if self.rejected_by is not None or self.reason is not None:
                raise InvalidRiskProfileApprovalError("an APPROVED approval cannot have rejected_by/reason")
            if self.resolved_at is None:
                raise InvalidRiskProfileApprovalError("an APPROVED approval must have resolved_at")

        if self.status == REJECTED:
            self._require_text(self.rejected_by, "rejected_by")
            self._require_text(self.reason, "reason")
            if self.approved_by is not None:
                raise InvalidRiskProfileApprovalError("a REJECTED approval cannot have approved_by")
            if self.resolved_at is None:
                raise InvalidRiskProfileApprovalError("a REJECTED approval must have resolved_at")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidRiskProfileApprovalError(f"{field_name} is required and must be non-blank")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["resolved_at"] = self.resolved_at.isoformat() if self.resolved_at else None
        return data


def new_approval_id() -> str:
    return str(uuid4())
