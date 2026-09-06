from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_policy_risk_decision import RiskDecision

# Same PENDING/APPROVED/REJECTED shape
# backend.session.execution_approval_request.ExecutionApprovalRequest
# already established (see backend.agent_policy_risk_approval.
# ApprovalRequirement, which reused it too as REQUIRED/APPROVED/
# REJECTED), plus EXPIRED for this service's own time-bound escalation
# window -- named PENDING here (not REQUIRED) per this commit's own
# goal wording, even though it plays the same "awaiting a human
# decision" role Commit #5's REQUIRED does for its own record.
PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
EXPIRED = "EXPIRED"
STATUSES = (PENDING, APPROVED, REJECTED, EXPIRED)


class InvalidEscalationError(ValueError):
    """Raised when an Escalation's fields are missing, invalid, or
    inconsistent with its own status."""


@dataclass(frozen=True)
class Escalation(object):
    """Immutable record of one Commit #5 ApprovalRequirement escalated
    for human review beyond the normal approval gate.

    Modeled on backend.agent_policy_risk_approval.ApprovalRequirement's
    own value-object shape (itself modeled on
    ExecutionApprovalRequest) -- a value object only, performing no
    state transition of its own; LLMAgentRiskEscalationService produces
    a new record (via dataclasses.replace) for every transition rather
    than mutating an existing one.

    decision and action_context are copied verbatim from the
    ApprovalRequirement this escalation was raised against -- "preserve
    the original risk decision" and "carry forward risk level, evidence,
    policy decision, and provenance" both mean this record never
    re-derives or summarizes any of it: decision.risk_level/risk_factors/
    reasons/provenance (Commit #4's own RiskDecision, which itself
    embeds Commit #1-#3's full chain) travel through unchanged.

    Attributes:
        escalation_id: This escalation's unique identifier
        request_id: The Commit #5 ApprovalRequirement.request_id this
            escalation was raised against
        scope_id: The scope this escalation belongs to, copied from the
            underlying requirement. Never consulted for, or leaked
            into, any other scope
        decision: The original Commit #4 RiskDecision, preserved
            verbatim
        action_context: A snapshot of the action_context the underlying
            requirement was scoped to
        reason: Why this was escalated. Required, and immutable for the
            life of the record regardless of how it is later resolved
            (unlike ApprovalRequirement's own reason, which only a
            REJECTED record carries, this reason documents the
            escalation itself, not its resolution)
        status: PENDING, APPROVED, REJECTED, or EXPIRED
        actor: Who resolved this escalation -- None while PENDING or
            once it lapses to EXPIRED (nobody decided an expired one)
        created_at: When this escalation was raised
        resolved_at: When this escalation was approved or rejected, or
            None while PENDING or EXPIRED
        expires_at: The deadline by which a PENDING escalation must be
            resolved, after which it is read as EXPIRED
        provenance: {request_id, decision, action_context}, the
            complete evidence this escalation carries forward -- the
            same "always expose an explicit provenance dict" convention
            every prior result type in this series already established
    """

    escalation_id: str
    request_id: str
    scope_id: str
    decision: RiskDecision
    action_context: dict
    reason: str
    status: str = PENDING
    actor: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        self._require_text(self.escalation_id, "escalation ID")
        self._require_text(self.request_id, "request ID")
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.reason, "reason")

        if not isinstance(self.decision, RiskDecision):
            raise InvalidEscalationError(
                f"decision must be a RiskDecision, got {type(self.decision).__name__}"
            )
        if not isinstance(self.action_context, dict):
            raise InvalidEscalationError(
                f"action_context must be a dict, got {type(self.action_context).__name__}"
            )
        if self.status not in STATUSES:
            raise InvalidEscalationError(f"status {self.status!r} is not one of {STATUSES}")

        if self.status == PENDING:
            if self.actor is not None or self.resolved_at is not None:
                raise InvalidEscalationError(
                    "a PENDING escalation cannot have an actor or resolved_at"
                )
            if not isinstance(self.expires_at, datetime):
                raise InvalidEscalationError("a PENDING escalation must have a datetime expires_at")

        if self.status == EXPIRED:
            if self.actor is not None or self.resolved_at is not None:
                raise InvalidEscalationError(
                    "an EXPIRED escalation cannot have an actor or resolved_at: nobody decided it"
                )

        if self.status in (APPROVED, REJECTED):
            self._require_text(self.actor, "actor")
            if self.resolved_at is None:
                raise InvalidEscalationError(f"a {self.status} escalation must have a resolved_at")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidEscalationError(f"{field_name} is required and must be non-blank")


def new_escalation_id() -> str:
    return str(uuid4())
