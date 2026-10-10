from dataclasses import replace
from datetime import datetime

from backend.agent_policy_risk_approval import (
    EXPIRED as APPROVAL_EXPIRED,
)
from backend.agent_policy_risk_approval import (
    REQUIRED as APPROVAL_REQUIRED,
)
from backend.agent_policy_risk_approval import (
    ApprovalRequirement,
    ApprovalRequirementStore,
    effective_status,
)
from backend.agent_policy_risk_escalation import (
    EXPIRED as ESCALATION_EXPIRED,
)
from backend.agent_policy_risk_escalation import (
    PENDING as ESCALATION_PENDING,
)
from backend.agent_policy_risk_escalation import (
    Escalation,
    EscalationStore,
)

# Which (pending_status, expired_status) pair governs each record type
# this service understands -- Commit #5's ApprovalRequirement and
# Commit #6's Escalation each use their own vocabulary (REQUIRED/EXPIRED
# vs PENDING/EXPIRED) for what is structurally the identical
# still-open/lapsed distinction.
_RECORD_KINDS = (
    (ApprovalRequirement, APPROVAL_REQUIRED, APPROVAL_EXPIRED),
    (Escalation, ESCALATION_PENDING, ESCALATION_EXPIRED),
)


class InvalidExpirationTargetError(TypeError):
    """Raised when is_expired() is given something other than a Commit
    #5 ApprovalRequirement or Commit #6 Escalation."""


class LLMAgentRiskExpirationService:
    """Explicit, on-demand expiration for Commit #5 ApprovalRequirement
    and Commit #6 Escalation records -- not a new scheduler or lifecycle
    framework: every rule this service enforces is the exact same
    pending/expired distinction Commit #5's own
    LLMAgentRiskApprovalGate._effective() and Commit #6's own
    LLMAgentRiskEscalationService._effective() already computed lazily
    at read time, now available as one canonical, reusable predicate
    (backend.agent_policy_risk_approval.effective_status(), extracted
    from Commit #5's own package and reused by Commit #6 -- see that
    function's own docstring) instead of three independent copies of
    the same comparison. This is what "integrate expiration into
    approval/escalation reads and authorization checks" means here:
    Commit #5/#6's own get()/approve()/reject()/resolve() already read
    through this exact same rule, since this commit's own contribution
    was pulling that rule out into one shared place rather than
    building a fourth copy of it for this service alone.

    is_expired(record, now) is a pure predicate -- it never mutates
    record or persists anything, and dispatches purely on record's own
    type to know which (pending_status, expired_status) pair applies
    (see Rules: "Expiration must be deterministic from stored
    timestamps": the same (record, now) always returns the same
    answer, and only created_at/expires_at/resolved_at -- fields both
    record types already carry from Commit #5/#6 -- are ever consulted,
    never a background clock or external state).

    expire_pending(scope_id, now) is the one genuinely new capability
    this commit adds: an explicit, caller-invoked sweep that durably
    persists the EXPIRED transition for every currently-pending,
    past-due record in one scope -- Commit #5/#6's own lazy checks
    compute an EXPIRED *view* on read but never write it back, so
    without this, a store's own list_for_scope() would keep showing a
    stale record as REQUIRED/PENDING forever until someone happens to
    read it individually. Per the goal's own "no background scheduler
    unless one already exists; expose an explicit expiration
    operation", this service triggers nothing on its own -- a caller
    (a cron job, an admin action, or a test) decides when to call it.

    Both operations are scope-isolated (only scope_id's own records are
    ever read or written) and never touch an already-resolved
    (APPROVED/REJECTED) record -- expire_pending() only ever considers a
    record whose own *stored* status is still the pending one for its
    type, so "already resolved decisions must not be rewritten by
    expiration" holds even for a record whose (now historical)
    expires_at has long since passed.
    """

    def __init__(self, approval_store: ApprovalRequirementStore, escalation_store: EscalationStore = None):
        """
        Args:
            approval_store: Commit #5's own ApprovalRequirementStore
            escalation_store: Optional Commit #6 EscalationStore --
                omit when a caller only wants approval expiration
        """
        self._approval_store = approval_store
        self._escalation_store = escalation_store

    def is_expired(self, request_or_escalation, now: datetime) -> bool:
        """Whether request_or_escalation currently reads as expired as
        of now -- False for anything not currently in its own pending
        status (already APPROVED/REJECTED, or not due yet).

        Raises:
            InvalidExpirationTargetError: If request_or_escalation is
                not an ApprovalRequirement or Escalation
        """
        for kind, pending_status, expired_status in _RECORD_KINDS:
            if isinstance(request_or_escalation, kind):
                computed = effective_status(
                    request_or_escalation.status,
                    request_or_escalation.expires_at,
                    pending_status,
                    expired_status,
                    now,
                )
                return computed == expired_status

        raise InvalidExpirationTargetError(
            "is_expired() only accepts an ApprovalRequirement or Escalation, got "
            f"{type(request_or_escalation).__name__}"
        )

    def expire_pending(self, scope_id: str, now: datetime) -> list:
        """Durably transition every currently-pending, past-due
        ApprovalRequirement/Escalation for scope_id to EXPIRED, and
        return exactly the records this call actually transitioned (in
        the order encountered: every expired ApprovalRequirement, then
        every expired Escalation).

        Raises:
            ValueError: If scope_id is missing or blank
        """
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("scope_id is required and must be a non-empty string")

        transitioned = []

        for requirement in self._approval_store.list_for_scope(scope_id):
            if requirement.status != APPROVAL_REQUIRED:
                continue
            if self.is_expired(requirement, now):
                expired = replace(requirement, status=APPROVAL_EXPIRED)
                self._approval_store.save(expired)
                transitioned.append(expired)

        if self._escalation_store is not None:
            for escalation in self._escalation_store.list_for_scope(scope_id):
                if escalation.status != ESCALATION_PENDING:
                    continue
                if self.is_expired(escalation, now):
                    expired = replace(escalation, status=ESCALATION_EXPIRED)
                    self._escalation_store.save(expired)
                    transitioned.append(expired)

        return transitioned
