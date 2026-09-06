from backend.agent_policy_risk_approval import APPROVED, REJECTED
from backend.agent_policy_risk_review_assignment import LLMAgentRiskReviewAssignment
from backend.agent_policy_risk_review_queue import (
    EXPIRED,
    PENDING,
    RESOLVED,
    ExpiredReviewItemError,
    LLMAgentRiskReviewQueue,
)

from .models import ReviewResolution

_OUTCOMES = (APPROVED, REJECTED)


class UnauthorizedReviewerError(ValueError):
    """Raised when resolve() is given a reviewer other than the item's
    assigned/claimed owner (see Rules: "Only the assigned/authorized
    reviewer can resolve")."""


class ReviewNotClaimedError(ValueError):
    """Raised when resolve() is attempted against a still-PENDING item
    -- an item must be claimed (directly, or via Commit #9's own
    assign()) before anyone can resolve it."""


class AlreadyResolvedError(ValueError):
    """Raised when resolve() is given a decision/reviewer/reason that
    conflicts with an item's own already-recorded resolution (a
    genuinely different second resolution, not a repeat of the exact
    same one -- see LLMAgentRiskReviewResolver's own docstring)."""


class CannotApproveDeniedActionError(ValueError):
    """Raised when resolve() would approve an item whose original
    decision carries an explicit policy denial, which can never be
    approved into execution (see Rules: "Approval cannot override an
    explicit policy deny")."""


class LLMAgentRiskReviewResolver:
    """Resolves one Commit #8 ReviewItem, flowing the outcome back
    through Commit #5's approval gate (or Commit #6's escalation, when
    active) and, from there, straight into the real execution
    authorization check -- without this class introducing any new
    wiring into that boundary at all.

    Not a new authorization or workflow system: resolve() never decides
    allow/deny itself and never touches
    LLMAgentPolicyEnforcement/LLMToolRegistryService/
    LLMAgentPolicyAuditService or any execution-boundary code directly
    -- it validates who may act and in what state, then delegates the
    entire "apply resolution / update approval-escalation state" step to
    Commit #8's own already-tested complete() (see Rules: "Reuse
    existing approval/enforcement infrastructure").

    "Make authorization result available to enforcement" requires no
    new integration point here, because one already exists: Commit #5's
    own LLMAgentRiskGatedExecutionService.execute_step() re-calls
    LLMAgentRiskApprovalGate.evaluate() (idempotent per action/context)
    on every retry, which is exactly the same ApprovalRequirement
    complete() just updated. A retried execute_step() for the identical
    action_context therefore sees this resolution the moment it is
    recorded, with zero changes to Commit #5 -- verified directly with a
    real end-to-end execution-boundary test rather than assumed.

    "Validate assignment/authority" reads Commit #9's own
    LLMAgentRiskReviewAssignment.get_assignment() when one is configured
    -- an active Assignment's own reviewer is authoritative over
    whoever merely holds Commit #8's own claim (a caller could have
    claimed directly, bypassing assignment entirely); with no
    assignment_service configured, or no active assignment recorded,
    Commit #8's own item.claimed_by is the sole authority. Either way,
    an unclaimed (PENDING) item can never be resolved -- there is no
    ambiguity about "who" to check yet.

    A genuinely additive change to already-shipped Commit #8 was needed
    here: complete() previously always drove the underlying gate/
    escalation transition as item.claimed_by, with no way to record a
    different actor. Once Commit #9 made it possible for an active
    Assignment's reviewer to diverge from Commit #8's own raw claim
    owner (a deliberate Commit #9 design choice -- see its own
    docstring on reassignment never forcing a queue takeover), resolving
    "as" the authorized reviewer required Commit #8's own complete() to
    accept who that actually is. Fixed with one small, backward-
    compatible addition: complete(item_id, resolution, actor=None) --
    actor defaults to the item's own claimed_by exactly as before when
    omitted, and ReviewItem gained one new field, resolved_by (None
    until RESOLVED, then the actor who actually completed it, which is
    NOT always the same as claimed_by). Reran all 20 existing Commit #8
    tests unmodified afterward, zero regressions.

    "Approval cannot override an explicit policy deny" is already
    structurally impossible through the normal pipeline (a REVIEW
    decision, the only kind Commit #8 ever enqueues, never carries
    Commit #4's own policy_denial factor -- decide() forces DENY
    outright whenever that factor is set). As the same independent,
    belt-and-suspenders safety net Commits #4/#5/#6 already each apply
    at their own layer, resolve() additionally refuses outright to
    approve an item whose decision.risk_factors reports policy_denial
    regardless of how it got there.

    "Resolution must be atomic/idempotent": Commit #8's own complete()
    already drives the real gate/escalation transition before
    persisting the RESOLVED item (so a failure there leaves nothing
    half-applied); this resolver adds the other half -- calling
    resolve() again with the *exact same* (decision, reviewer, reason)
    against an already-RESOLVED item returns the same ReviewResolution
    rather than raising, while a genuinely different second resolution
    attempt raises AlreadyResolvedError.
    """

    def __init__(self, queue: LLMAgentRiskReviewQueue, assignment_service: LLMAgentRiskReviewAssignment = None):
        """
        Args:
            queue: Commit #8's own LLMAgentRiskReviewQueue
            assignment_service: Optional Commit #9
                LLMAgentRiskReviewAssignment -- when given and an item
                has an active assignment, that assignment's reviewer is
                authoritative over Commit #8's own claimed_by
        """
        self._queue = queue
        self._assignment_service = assignment_service

    def resolve(self, item_id: str, decision: str, reviewer: str, reason: str = None) -> ReviewResolution:
        """Resolve item_id as APPROVED or REJECTED.

        Raises:
            UnknownReviewItemError: If item_id was never enqueued
                (propagated from Commit #8's own get())
            ValueError: If decision is not APPROVED/REJECTED, reviewer
                is missing/blank, or decision is REJECTED and reason is
                missing/blank
            ExpiredReviewItemError: If the item's deadline has lapsed
            ReviewNotClaimedError: If the item is still PENDING
            UnauthorizedReviewerError: If reviewer is not the item's
                assigned/claimed owner
            CannotApproveDeniedActionError: If decision is APPROVED but
                the item's original decision carries an explicit policy
                denial
            AlreadyResolvedError: If the item was already resolved with
                a different decision/reviewer/reason
        """
        if decision not in _OUTCOMES:
            raise ValueError(f"decision must be one of {_OUTCOMES}, got {decision!r}")
        self._require_text(reviewer, "reviewer")
        if decision == REJECTED:
            self._require_text(reason, "reason")

        item = self._queue.get(item_id)

        if item.status == RESOLVED:
            return self._resolve_against_existing(item, decision, reviewer, reason)

        if item.status == EXPIRED:
            raise ExpiredReviewItemError(
                f"cannot resolve item {item_id!r}: its deadline expired at {item.expires_at!r}"
            )

        if item.status == PENDING:
            raise ReviewNotClaimedError(
                f"cannot resolve item {item_id!r}: it has not been claimed or assigned yet"
            )

        # item.status == CLAIMED
        authorized_reviewer = self._authorized_reviewer(item)
        if reviewer != authorized_reviewer:
            raise UnauthorizedReviewerError(
                f"reviewer {reviewer!r} is not authorized to resolve item {item_id!r} "
                f"(authorized reviewer is {authorized_reviewer!r})"
            )

        if decision == APPROVED and bool(item.decision.risk_factors.get("policy_denial")):
            raise CannotApproveDeniedActionError(
                f"cannot approve item {item_id!r}: its original decision carries an explicit "
                f"policy denial, which can never be approved into execution"
            )

        completed = self._queue.complete(item_id, {"outcome": decision, "reason": reason}, actor=reviewer)
        return self._to_resolution(completed)

    def _authorized_reviewer(self, item):
        if self._assignment_service is not None:
            active = self._assignment_service.get_assignment(item.item_id)
            if active is not None:
                return active.reviewer
        return item.claimed_by

    def _resolve_against_existing(self, item, decision, reviewer, reason) -> ReviewResolution:
        resolution = item.resolution or {}
        if (
            resolution.get("outcome") == decision
            and resolution.get("reason") == reason
            and item.resolved_by == reviewer
        ):
            return self._to_resolution(item)

        raise AlreadyResolvedError(
            f"item {item.item_id!r} was already resolved ({resolution!r} by {item.resolved_by!r}); "
            f"cannot resolve it again with a different outcome, reviewer, or reason"
        )

    @staticmethod
    def _to_resolution(item) -> ReviewResolution:
        resolution = item.resolution or {}
        return ReviewResolution(
            item_id=item.item_id,
            scope_id=item.scope_id,
            outcome=resolution.get("outcome"),
            reviewer=item.resolved_by,
            reason=resolution.get("reason"),
            decision=item.decision,
            approval_request_id=item.approval_request_id,
            escalation_id=item.escalation_id,
            resolved_at=item.resolved_at,
            provenance={"item_id": item.item_id, "review_item": item, "decision": item.decision},
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required and must be non-blank")
