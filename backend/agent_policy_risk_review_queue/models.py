from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_policy_risk_decision import RiskDecision

# pending | claimed | resolved | expired, per this commit's own goal
# wording -- structurally the same lifecycle Commit #5's
# ApprovalRequirement (REQUIRED/APPROVED/REJECTED/EXPIRED) and Commit
# #6's Escalation (PENDING/APPROVED/REJECTED/EXPIRED) already use, with
# one genuine addition neither of those needs: CLAIMED, the ownership
# state a review item passes through between being unclaimed and being
# completed (see Rules: "Claiming must prevent conflicting reviewers
# from simultaneously owning the item").
PENDING = "PENDING"
CLAIMED = "CLAIMED"
RESOLVED = "RESOLVED"
EXPIRED = "EXPIRED"
STATUSES = (PENDING, CLAIMED, RESOLVED, EXPIRED)

# The two non-terminal statuses a review item can still lapse from --
# fed straight into backend.agent_policy_risk_approval.effective_status()
# (broadened in Commit #7/#8 to accept more than one pending status)
# rather than a fifth copy of the expiry comparison.
OPEN_STATUSES = (PENDING, CLAIMED)


class InvalidReviewItemError(ValueError):
    """Raised when a ReviewItem's fields are missing, invalid, or
    inconsistent with its own status."""


@dataclass(frozen=True)
class ReviewItem(object):
    """Immutable record of one Commit #4 REVIEW RiskDecision queued for
    human review, connecting it to Commit #5's ApprovalRequirement (and,
    once escalated, Commit #6's Escalation) rather than deciding
    authorization itself.

    Modeled on ApprovalRequirement/Escalation's own value-object shape
    (status-consistency validation, dataclasses.replace()-not-mutate) --
    a value object only; LLMAgentRiskReviewQueue is what enqueues,
    claims, and completes items.

    decision and action_context are copied verbatim from the Commit #5
    ApprovalRequirement this item was enqueued from (see Rules:
    "Preserve risk level, decision, evidence, ... and provenance") --
    decision.risk_level/risk_factors/reasons/provenance travel through
    unchanged. approval_request_id and escalation_id are references,
    never copies, back to the real Commit #5/#6 records that actually
    govern authorization -- LLMAgentRiskReviewQueue.complete() acts
    through those records via their own services, never by deciding
    allow/deny on this item's own say-so (see Rules: "Resolution must
    flow through existing approval/escalation rules").

    Attributes:
        item_id: This item's unique identifier
        scope_id: The scope this item belongs to, copied from the
            underlying requirement. Never consulted for, or leaked
            into, any other scope
        decision: The original Commit #4 RiskDecision, preserved
            verbatim
        action_context: A snapshot of the action_context the underlying
            requirement is scoped to
        approval_request_id: The Commit #5 ApprovalRequirement.request_id
            this item was enqueued from
        escalation_id: The Commit #6 Escalation.escalation_id this item
            was escalated to, or None if it never was
        status: PENDING, CLAIMED, RESOLVED, or EXPIRED
        claimed_by: Who currently owns this item -- None until claimed,
            and never cleared once set (even once RESOLVED or EXPIRED,
            so "who was working this" is never lost)
        claimed_at: When this item was claimed, or None if it never was
        resolution: {"outcome": APPROVED/REJECTED, "reason": str or
            None} once RESOLVED, else None
        resolved_by: Who actually completed this item -- normally the
            same as claimed_by, but can differ (e.g. Commit #9's own
            assignment authority diverging from Commit #8's own real
            claim owner); None until RESOLVED
        resolved_at: When this item was resolved, or None otherwise
        created_at: When this item was enqueued
        expires_at: The deadline by which this item must be resolved,
            after which it is read as EXPIRED regardless of PENDING/
            CLAIMED
        provenance: {approval_request_id, escalation_id, decision,
            action_context} -- the complete evidence this item carries
            forward, the same explicit provenance-dict convention every
            prior result type in this series already established
    """

    item_id: str
    scope_id: str
    decision: RiskDecision
    action_context: dict
    approval_request_id: str
    escalation_id: Optional[str] = None
    status: str = PENDING
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    resolution: Optional[dict] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        self._require_text(self.item_id, "item ID")
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.approval_request_id, "approval request ID")

        if not isinstance(self.decision, RiskDecision):
            raise InvalidReviewItemError(
                f"decision must be a RiskDecision, got {type(self.decision).__name__}"
            )
        if not isinstance(self.action_context, dict):
            raise InvalidReviewItemError(
                f"action_context must be a dict, got {type(self.action_context).__name__}"
            )
        if self.status not in STATUSES:
            raise InvalidReviewItemError(f"status {self.status!r} is not one of {STATUSES}")

        if self.status == PENDING:
            if self.claimed_by is not None or self.claimed_at is not None:
                raise InvalidReviewItemError("a PENDING item cannot have a claimed_by or claimed_at")
            if self.resolution is not None or self.resolved_at is not None:
                raise InvalidReviewItemError("a PENDING item cannot have a resolution or resolved_at")
            if not isinstance(self.expires_at, datetime):
                raise InvalidReviewItemError("a PENDING item must have a datetime expires_at")

        if self.status == CLAIMED:
            self._require_text(self.claimed_by, "claimed_by")
            if not isinstance(self.claimed_at, datetime):
                raise InvalidReviewItemError("a CLAIMED item must have a datetime claimed_at")
            if self.resolution is not None or self.resolved_at is not None:
                raise InvalidReviewItemError("a CLAIMED item cannot have a resolution or resolved_at")

        if self.status == RESOLVED:
            self._require_text(self.claimed_by, "claimed_by")
            self._require_text(self.resolved_by, "resolved_by")
            if not isinstance(self.resolution, dict) or "outcome" not in self.resolution:
                raise InvalidReviewItemError("a RESOLVED item must have a resolution with an outcome")
            if self.resolved_at is None:
                raise InvalidReviewItemError("a RESOLVED item must have a resolved_at")

        if self.status == EXPIRED:
            if self.resolution is not None or self.resolved_at is not None:
                raise InvalidReviewItemError(
                    "an EXPIRED item cannot have a resolution or resolved_at: nobody completed it"
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidReviewItemError(f"{field_name} is required and must be non-blank")


def new_item_id() -> str:
    return str(uuid4())
