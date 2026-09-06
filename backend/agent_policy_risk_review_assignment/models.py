from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Same ACTIVE/REVOKED shape backend.agent_policy_exceptions.
# LLMAgentPolicyException already established for this series' other
# explicit, revocable grant (itself modeled on
# backend.session.execution_policy_risk_override's own enabled/disabled
# discipline) -- a revoked assignment is retained, never deleted, so
# "reassignment preserves history" holds by construction: reassigning
# never overwrites or removes the prior record, it only appends a new
# REVOKED one and a new ACTIVE one.
ACTIVE = "ACTIVE"
REVOKED = "REVOKED"
STATUSES = (ACTIVE, REVOKED)


class InvalidAssignmentError(ValueError):
    """Raised when an Assignment's fields are missing, invalid, or
    inconsistent with its own status."""


@dataclass(frozen=True)
class Assignment(object):
    """Immutable record of one reviewer's ownership of one Commit #8
    ReviewItem.

    A value object only, performing no state transition of its own --
    LLMAgentRiskReviewAssignment produces a new record (via
    dataclasses.replace) for every transition rather than mutating an
    existing one, the same discipline every prior value object in this
    series already keeps.

    Attributes:
        assignment_id: This assignment's unique identifier
        item_id: The Commit #8 ReviewItem.item_id this assignment
            governs
        scope_id: The scope this assignment belongs to, copied from the
            underlying review item. Never consulted for, or leaked
            into, any other scope
        reviewer: Who this assignment grants ownership to
        assigned_by: Who made this assignment -- the reviewer
            themselves for a self-service claim-via-assign, or a
            distinct actor for an administrative (re)assignment
        status: ACTIVE or REVOKED
        assigned_at: When this assignment was made
        revoked_at: When this assignment was revoked (by unassign() or
            superseded by a reassignment), or None while ACTIVE
        provenance: {item_id, scope_id, reviewer, assigned_by,
            review_item}, embedding the full Commit #8 ReviewItem this
            assignment was made against verbatim -- the same "embed a
            prior commit's full result, never re-summarize" convention
            this series has kept since Commit #2
    """

    assignment_id: str
    item_id: str
    scope_id: str
    reviewer: str
    assigned_by: str
    status: str = ACTIVE
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: Optional[datetime] = None
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        self._require_text(self.assignment_id, "assignment ID")
        self._require_text(self.item_id, "item ID")
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.reviewer, "reviewer")
        self._require_text(self.assigned_by, "assigned_by")

        if self.status not in STATUSES:
            raise InvalidAssignmentError(f"status {self.status!r} is not one of {STATUSES}")

        if self.status == ACTIVE and self.revoked_at is not None:
            raise InvalidAssignmentError("an ACTIVE assignment cannot have a revoked_at")
        if self.status == REVOKED and self.revoked_at is None:
            raise InvalidAssignmentError("a REVOKED assignment must have a revoked_at")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidAssignmentError(f"{field_name} is required and must be non-blank")


def new_assignment_id() -> str:
    return str(uuid4())
