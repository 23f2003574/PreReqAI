from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.agent_policy_risk_decision import RiskDecision

# The reserved actor recorded for a requirement this gate resolved
# itself (an ALLOW bypass, or a DENY auto-rejection) rather than a real
# human decision -- so "who decided this" is always answerable, never a
# blank/None actor pretending to be a human one.
SYSTEM_ACTOR = "system"

REQUIRED = "REQUIRED"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
EXPIRED = "EXPIRED"
STATUSES = (REQUIRED, APPROVED, REJECTED, EXPIRED)


class InvalidApprovalRequirementError(ValueError):
    """Raised when an ApprovalRequirement's fields are missing, invalid,
    or inconsistent with its own status."""


@dataclass(frozen=True)
class ApprovalRequirement(object):
    """Immutable record of one Commit #4 RiskDecision's approval state
    for one specific action_context.

    Modeled directly on backend.session.execution_approval_request.
    ExecutionApprovalRequest -- a value object only, performing no state
    transition of its own; LLMAgentRiskApprovalGate produces a new
    record (via dataclasses.replace) for every transition rather than
    mutating an existing one, the same "terminal once decided" discipline
    that precedent already established (extended here with EXPIRED, the
    one status that precedent does not have, for this gate's own
    time-bound REQUIRED window).

    decision is Commit #4's own RiskDecision, embedded verbatim --
    "preserve actor, decision, risk evidence, and timestamps" means this
    requirement never re-summarizes or drops any of it (risk_factors and
    reasons already travel inside decision itself). action_context is a
    snapshot of exactly what this requirement was scoped to, so "approval
    must be scoped to the specific action/context" is always verifiable
    by inspection, not merely assumed from scope_id alone.

    Attributes:
        request_id: This requirement's unique identifier
        scope_id: The scope this requirement belongs to. Never
            consulted for, or leaked into, any other scope
        status: REQUIRED, APPROVED, REJECTED, or EXPIRED
        decision: The Commit #4 RiskDecision this requirement was
            evaluated from
        action_context: A snapshot of the action_context this
            requirement is scoped to
        actor: Who approved or rejected this requirement -- SYSTEM_ACTOR
            for an ALLOW-bypass or DENY-auto-rejection, a real actor
            identifier once a human decides one, or None while REQUIRED
            or once it lapses to EXPIRED (nobody decided an expired one)
        reason: Why a REJECTED requirement was rejected. Required for
            REJECTED, never present otherwise
        created_at: When this requirement was created
        resolved_at: When this requirement was approved or rejected, or
            None while REQUIRED or EXPIRED
        expires_at: The deadline by which a REQUIRED requirement must be
            decided, after which it is read as EXPIRED. None for an
            ALLOW-bypass/DENY-auto-rejection, which are decided
            immediately and have no window to lapse
    """

    request_id: str
    scope_id: str
    status: str
    decision: RiskDecision
    action_context: dict
    actor: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        self._require_text(self.request_id, "request ID")
        self._require_text(self.scope_id, "scope ID")

        if not isinstance(self.decision, RiskDecision):
            raise InvalidApprovalRequirementError(
                f"decision must be a RiskDecision, got {type(self.decision).__name__}"
            )
        if not isinstance(self.action_context, dict):
            raise InvalidApprovalRequirementError(
                f"action_context must be a dict, got {type(self.action_context).__name__}"
            )

        if self.status not in STATUSES:
            raise InvalidApprovalRequirementError(
                f"status {self.status!r} is not one of {STATUSES}"
            )

        if self.status == REQUIRED:
            if self.actor is not None or self.resolved_at is not None or self.reason is not None:
                raise InvalidApprovalRequirementError(
                    "a REQUIRED requirement cannot have an actor, resolved_at, or reason"
                )
            if not isinstance(self.expires_at, datetime):
                raise InvalidApprovalRequirementError(
                    "a REQUIRED requirement must have a datetime expires_at"
                )

        if self.status == EXPIRED:
            if self.actor is not None or self.resolved_at is not None:
                raise InvalidApprovalRequirementError(
                    "an EXPIRED requirement cannot have an actor or resolved_at: nobody decided it"
                )

        if self.status in (APPROVED, REJECTED):
            self._require_text(self.actor, "actor")
            if self.resolved_at is None:
                raise InvalidApprovalRequirementError(
                    f"a {self.status} requirement must have a resolved_at"
                )

        if self.status == REJECTED:
            self._require_text(self.reason, "reason")
        elif self.reason is not None:
            raise InvalidApprovalRequirementError(
                "only a REJECTED requirement can have a reason"
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidApprovalRequirementError(f"{field_name} is required and must be non-blank")


def new_request_id() -> str:
    return str(uuid4())
