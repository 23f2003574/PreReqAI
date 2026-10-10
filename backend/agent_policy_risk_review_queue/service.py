from dataclasses import replace
from datetime import datetime, timezone

from backend.agent_policy_risk_approval import (
    APPROVED as APPROVAL_APPROVED,
)
from backend.agent_policy_risk_approval import (
    REJECTED as APPROVAL_REJECTED,
)
from backend.agent_policy_risk_approval import (
    REQUIRED as APPROVAL_REQUIRED,
)
from backend.agent_policy_risk_approval import (
    LLMAgentRiskApprovalGate,
    effective_status,
)
from backend.agent_policy_risk_decision import RiskDecision
from backend.agent_policy_risk_escalation import PENDING as ESCALATION_PENDING
from backend.agent_policy_risk_escalation import LLMAgentRiskEscalationService
from backend.agent_policy_risk_thresholds import REVIEW

from .in_memory_store import InMemoryReviewQueueStore
from .models import CLAIMED, EXPIRED, OPEN_STATUSES, PENDING, RESOLVED, ReviewItem, new_item_id
from .store import ReviewQueueStore

_OUTCOMES = (APPROVAL_APPROVED, APPROVAL_REJECTED)


class NotReviewableError(ValueError):
    """Raised when enqueue() is given a decision/action that is not
    actually a REVIEW decision currently REQUIRED in Commit #5's own
    gate (see Rules: "Only review decisions enter the queue")."""


class UnknownReviewItemError(KeyError):
    """Raised when get()/claim()/complete() is given an item_id that was
    never enqueued."""


class InvalidReviewItemTransitionError(ValueError):
    """Raised when claim()/complete() is attempted against an item that
    is not in a state that permits it."""


class ConflictingClaimError(InvalidReviewItemTransitionError):
    """Raised when claim() is attempted by an actor other than the one
    who already claimed the item (see Rules: "Claiming must prevent
    conflicting reviewers from simultaneously owning the item")."""


class ExpiredReviewItemError(InvalidReviewItemTransitionError):
    """Raised when claim()/complete() is attempted against an item whose
    deadline has lapsed (see Rules: "Expired items cannot be resolved
    into authorization")."""


class LLMAgentRiskReviewQueue:
    """A persistent queue connecting Commit #4 REVIEW RiskDecisions to
    Commit #5's approval gate and, when escalated, Commit #6's
    escalation service -- not a new workflow engine: this queue never
    decides authorization itself. enqueue() only ever wraps Commit #5's
    own LLMAgentRiskApprovalGate.evaluate() (the same idempotent,
    action/context-scoped call Commit #5 already exposes), and
    complete() only ever drives Commit #5's approve()/reject() (or,
    when an active Commit #6 escalation exists for the same
    approval_request_id, Commit #6's own resolve(), which itself drives
    Commit #5) -- see Rules: "Resolution must flow through existing
    approval/escalation rules" / "Do not create another workflow
    system".

    claim() establishes exclusive ownership before a review can be
    completed: an item PENDING may be claimed by any actor; an item
    already CLAIMED may only be re-claimed by the same actor (a no-op,
    satisfying "Queue operations must be idempotent where applicable")
    -- a different actor's claim() is rejected outright with
    ConflictingClaimError, so two reviewers can never simultaneously
    believe they own the same item. complete() then requires the item
    to be CLAIMED (by the actor completing it -- claim() and complete()
    are not separately actor-checked because the item's own claimed_by
    already names the sole owner permitted to complete it).

    Expiration reuses Commit #7's own canonical
    backend.agent_policy_risk_approval.effective_status() predicate
    (broadened in this commit to accept more than one "still open"
    status) rather than a fifth independent copy of the pending/expired
    comparison -- OPEN_STATUSES = (PENDING, CLAIMED) is this queue's own
    two non-terminal statuses, either of which can lapse into EXPIRED.
    Like every prior commit in this series, expiry is computed lazily
    at read time (get()/list()/claim()/complete()), never a persisted
    background mutation.

    Only an InMemory store is provided, for the same reason every other
    store in this sub-series gives (a durable ReviewItem embeds a full
    RiskDecision, not built for JSON round-tripping).
    """

    def __init__(
        self,
        approval_gate: LLMAgentRiskApprovalGate,
        store: ReviewQueueStore = None,
        escalation_service: LLMAgentRiskEscalationService = None,
    ):
        """
        Args:
            approval_gate: Commit #5's LLMAgentRiskApprovalGate --
                required, since every enqueue()/complete() call reads or
                drives it
            escalation_service: Optional Commit #6
                LLMAgentRiskEscalationService -- when given, complete()
                checks it for an active escalation on the item's own
                approval_request_id and, if one exists, resolves through
                it instead of the gate directly
        """
        self._approval_gate = approval_gate
        self.store = store if store is not None else InMemoryReviewQueueStore()
        self._escalation_service = escalation_service

    def enqueue(self, decision: RiskDecision, action_context: dict) -> ReviewItem:
        """Enqueue a REVIEW decision for human review, reusing (or
        creating) Commit #5's own ApprovalRequirement for this exact
        action_context.

        Idempotent: calling this again for the identical action_context
        while the resulting item is still live (PENDING, CLAIMED, or
        already RESOLVED) returns that same item rather than enqueuing a
        duplicate (see Rules: "Queue operations must be idempotent
        where applicable").

        Raises:
            NotReviewableError: If decision.decision is not REVIEW, or
                the underlying Commit #5 requirement is not REQUIRED
        """
        if not isinstance(decision, RiskDecision):
            raise NotReviewableError(f"decision must be a RiskDecision, got {type(decision).__name__}")
        if decision.decision != REVIEW:
            raise NotReviewableError(
                f"only REVIEW decisions may be enqueued, got {decision.decision!r}"
            )

        requirement = self._approval_gate.evaluate(decision, action_context)

        # Idempotency is checked before the REQUIRED guard below: once
        # an item already exists for this exact request_id, a repeated
        # enqueue() always returns it as-is -- PENDING, CLAIMED, or even
        # already RESOLVED -- rather than re-validating the requirement
        # a second time. Only when no live item exists yet does a fresh
        # requirement actually need to be REQUIRED to enqueue from.
        existing_id = self.store.current_for_request(requirement.request_id)
        if existing_id is not None:
            existing = self._effective(self.store.get(existing_id))
            if existing is not None and existing.status != EXPIRED:
                return existing

        if requirement.status != APPROVAL_REQUIRED:
            raise NotReviewableError(
                f"cannot enqueue: underlying request {requirement.request_id!r} is "
                f"{requirement.status!r}, not {APPROVAL_REQUIRED!r}"
            )

        item = ReviewItem(
            item_id=new_item_id(),
            scope_id=requirement.scope_id,
            decision=requirement.decision,
            action_context=dict(requirement.action_context),
            approval_request_id=requirement.request_id,
            expires_at=requirement.expires_at,
            provenance={
                "approval_request_id": requirement.request_id,
                "escalation_id": None,
                "decision": requirement.decision,
                "action_context": dict(requirement.action_context),
            },
        )
        self.store.save(item)
        self.store.set_current_for_request(requirement.request_id, item.item_id)
        return item

    def get(self, item_id: str) -> ReviewItem:
        """The item's current, effective state -- PENDING/CLAIMED reads
        as EXPIRED once its deadline has lapsed.

        Raises:
            UnknownReviewItemError: If item_id was never enqueued
        """
        stored = self.store.get(item_id)
        if stored is None:
            raise UnknownReviewItemError(item_id)
        return self._effective(stored)

    def list(self, scope_id: str, status: str = None) -> list:
        """Every item for scope_id, in enqueue order, each read through
        the same effective-status computation get() uses -- optionally
        filtered to one status.

        Raises:
            ValueError: If scope_id is missing or blank
        """
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("scope_id is required and must be a non-empty string")

        items = [self._effective(item) for item in self.store.list_for_scope(scope_id)]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def claim(self, item_id: str, actor: str) -> ReviewItem:
        """Claim exclusive ownership of a PENDING (or already-claimed-by-
        this-same-actor) item.

        Raises:
            UnknownReviewItemError: If item_id was never enqueued
            ValueError: If actor is missing or blank
            ExpiredReviewItemError: If the item's deadline has lapsed
            ConflictingClaimError: If another actor already claimed it
            InvalidReviewItemTransitionError: If the item is already
                RESOLVED
        """
        self._require_text(actor, "actor")

        stored = self.store.get(item_id)
        if stored is None:
            raise UnknownReviewItemError(item_id)

        effective = self._effective(stored)
        if effective.status == EXPIRED:
            raise ExpiredReviewItemError(
                f"cannot claim item {item_id!r}: its deadline expired at {stored.expires_at!r}"
            )
        if effective.status == RESOLVED:
            raise InvalidReviewItemTransitionError(f"cannot claim item {item_id!r}: it is RESOLVED")
        if effective.status == CLAIMED:
            if effective.claimed_by == actor:
                return effective
            raise ConflictingClaimError(
                f"cannot claim item {item_id!r}: already claimed by {effective.claimed_by!r}"
            )

        claimed = replace(
            stored, status=CLAIMED, claimed_by=actor, claimed_at=datetime.now(timezone.utc)
        )
        return self.store.save(claimed)

    def complete(self, item_id: str, resolution: dict, actor: str = None) -> ReviewItem:
        """Complete a CLAIMED item, driving the real authorization
        transition through Commit #5's gate (or, when an active Commit
        #6 escalation exists for the same request, through Commit #6's
        own resolve()) -- never deciding allow/deny on this item's own
        say-so.

        resolution is {"outcome": APPROVED or REJECTED (Commit #5's own
        constants), "reason": str, required when outcome is REJECTED}.

        actor is who is recorded as having actually completed this item
        (resolved_by) and driven the underlying gate/escalation
        transition -- defaulting to the item's own claimed_by, but
        overridable for a caller (Commit #10's own
        LLMAgentRiskReviewResolver) whose own authorization source (e.g.
        Commit #9's active Assignment) has determined a different actor
        is the one actually authorized to complete it than whoever
        happens to hold Commit #8's own raw claim.

        Raises:
            UnknownReviewItemError: If item_id was never enqueued
            ValueError: If resolution is malformed
            ExpiredReviewItemError: If the item's deadline has lapsed
            InvalidReviewItemTransitionError: If the item is not
                currently CLAIMED
        """
        if not isinstance(resolution, dict) or resolution.get("outcome") not in _OUTCOMES:
            raise ValueError(f"resolution must be a dict with an outcome in {_OUTCOMES}")
        outcome = resolution["outcome"]
        reason = resolution.get("reason")
        if outcome == APPROVAL_REJECTED:
            self._require_text(reason, "resolution['reason']")

        stored = self.store.get(item_id)
        if stored is None:
            raise UnknownReviewItemError(item_id)

        effective = self._effective(stored)
        if effective.status == EXPIRED:
            raise ExpiredReviewItemError(
                f"cannot complete item {item_id!r}: its deadline expired at {stored.expires_at!r}"
            )
        if effective.status != CLAIMED:
            raise InvalidReviewItemTransitionError(
                f"cannot complete item {item_id!r}: it is {effective.status}, not {CLAIMED}"
            )

        resolved_by = actor or effective.claimed_by
        escalation_id = self._active_escalation_id(effective.approval_request_id)

        if escalation_id is not None:
            self._escalation_service.resolve(escalation_id, outcome, resolved_by, resolution_reason=reason)
        elif outcome == APPROVAL_APPROVED:
            self._approval_gate.approve(effective.approval_request_id, resolved_by)
        else:
            self._approval_gate.reject(effective.approval_request_id, resolved_by, reason)

        resolved = replace(
            stored,
            status=RESOLVED,
            escalation_id=escalation_id or stored.escalation_id,
            resolution={"outcome": outcome, "reason": reason},
            resolved_by=resolved_by,
            resolved_at=datetime.now(timezone.utc),
        )
        return self.store.save(resolved)

    def _active_escalation_id(self, approval_request_id: str):
        if self._escalation_service is None:
            return None
        active_id = self._escalation_service.store.active_for_request(approval_request_id)
        if active_id is None:
            return None
        active = self._escalation_service.get(active_id)
        return active.escalation_id if active.status == ESCALATION_PENDING else None

    @staticmethod
    def _effective(item, now=None):
        if item is None:
            return None

        now = now or datetime.now(timezone.utc)
        new_status = effective_status(item.status, item.expires_at, OPEN_STATUSES, EXPIRED, now)
        if new_status == item.status:
            return item
        return replace(item, status=new_status)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required and must be non-blank")
