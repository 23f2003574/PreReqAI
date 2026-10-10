from dataclasses import replace
from datetime import datetime, timezone

from backend.agent_policy_risk_review_queue import (
    EXPIRED,
    RESOLVED,
    ConflictingClaimError,
    ExpiredReviewItemError,
    InvalidReviewItemTransitionError,
    LLMAgentRiskReviewQueue,
    UnknownReviewItemError,
)

from .in_memory_store import InMemoryAssignmentStore
from .models import ACTIVE, REVOKED, Assignment, new_assignment_id
from .store import AssignmentStore

_TERMINAL_ITEM_STATUSES = (RESOLVED, EXPIRED)


class UnauthorizedReviewerError(ValueError):
    """Raised when assign() is given a reviewer the caller's own
    authorization collaborator does not authorize for the item's scope
    (see Rules: "Reviewer must be authorized for the item's scope")."""


class AssignmentNotAllowedError(ValueError):
    """Raised when assign() targets an item that is EXPIRED or RESOLVED
    (see Rules: "Expired/resolved items cannot be assigned")."""


class NotAssignedError(ValueError):
    """Raised when unassign() is given a reviewer who does not currently
    hold the item's active assignment."""


class LLMAgentRiskReviewAssignment:
    """Explicit reviewer assignment layered on top of Commit #8's
    review queue -- not a new reviewer or authorization system: this
    service owns no notion of who is *allowed* to review a scope (see
    Rules: "Reviewer must be authorized for the item's scope";
    Constraints: "No new authorization system") and no notion of
    exclusive item ownership beyond what Commit #8's own
    LLMAgentRiskReviewQueue.claim() already enforces (see Rules: "Only
    one active reviewer owns an item" -- read here as "one active
    Assignment", integrated with, not duplicating, Commit #8's own
    "one active claim").

    reviewer_authorization is a required, duck-typed collaborator --
    any callable `(reviewer, scope_id) -> bool` -- exactly the same
    "no authorization mechanism already exists for this, so require an
    explicit, caller-supplied one rather than inventing a framework or
    silently allowing everyone" resolution the base series' own
    LLMAgentPolicyDeploymentOrchestrator already reached for its own
    `rollback_authorization` callable. This service never decides who
    *may* review a scope; it only ever asks.

    assign() reuses Commit #8's own get() to read (never re-derive) an
    item's current, effective status -- an EXPIRED or RESOLVED item
    (Commit #8's own lazy expiry/resolution) can never be assigned (see
    Rules: "Expired/resolved items cannot be assigned"), and this is
    checked by asking Commit #8, never by this service's own copy of
    expiry logic. On a successful assignment, this service also
    attempts Commit #8's own claim(item_id, reviewer) on the reviewer's
    behalf (see Rules: "Integrate assignment with queue claiming ...")
    -- the common case (an unclaimed or already-self-claimed item) picks
    up real queue ownership immediately; if the item is already CLAIMED
    by someone else, that ConflictingClaimError is swallowed rather than
    forcing a takeover Commit #8 was never built to support --
    "reassignment" at this layer records who is now responsible without
    ever bypassing Commit #8's own conflict-prevention. "Unassigned
    items remain claimable" holds because this service places no
    restriction of its own on Commit #8's claim() at all -- an item with
    no ACTIVE assignment is claimable by anyone exactly as Commit #8
    already allows.

    Reassignment (assign() called for a different reviewer while an
    ACTIVE assignment already exists) revokes the prior assignment
    (status=REVOKED, revoked_at set) and creates a new ACTIVE one,
    never mutating or deleting the old record -- "reassignment preserves
    history" holds structurally, verifiable via history(item_id).
    Assigning the *same* reviewer who already holds the active
    assignment is idempotent: it returns the existing record unchanged.
    """

    def __init__(
        self,
        queue: LLMAgentRiskReviewQueue,
        reviewer_authorization,
        store: AssignmentStore = None,
    ):
        """
        Args:
            queue: Commit #8's own LLMAgentRiskReviewQueue
            reviewer_authorization: Required callable `(reviewer,
                scope_id) -> bool`, consulted by assign() before
                granting ownership
            store: Optional AssignmentStore, defaulting to an in-memory
                one
        """
        self._queue = queue
        self._reviewer_authorization = reviewer_authorization
        self.store = store if store is not None else InMemoryAssignmentStore()

    def assign(self, item_id: str, reviewer: str, assigned_by: str = None) -> Assignment:
        """Assign reviewer as the owner of item_id.

        Raises:
            UnknownReviewItemError: If item_id was never enqueued
                (propagated from Commit #8's own get())
            ValueError: If reviewer is missing or blank
            AssignmentNotAllowedError: If the item is EXPIRED or RESOLVED
            UnauthorizedReviewerError: If reviewer_authorization does not
                authorize reviewer for the item's scope
        """
        self._require_text(reviewer, "reviewer")
        item = self._queue.get(item_id)  # UnknownReviewItemError propagates as-is

        if item.status in _TERMINAL_ITEM_STATUSES:
            raise AssignmentNotAllowedError(
                f"cannot assign item {item_id!r}: it is {item.status}"
            )
        if not self._reviewer_authorization(reviewer, item.scope_id):
            raise UnauthorizedReviewerError(
                f"reviewer {reviewer!r} is not authorized for scope {item.scope_id!r}"
            )

        current = self._active(item_id)
        if current is not None and current.reviewer == reviewer:
            return current

        now = datetime.now(timezone.utc)
        if current is not None:
            self.store.save(replace(current, status=REVOKED, revoked_at=now))

        assignment = Assignment(
            assignment_id=new_assignment_id(),
            item_id=item_id,
            scope_id=item.scope_id,
            reviewer=reviewer,
            assigned_by=assigned_by or reviewer,
            assigned_at=now,
            provenance={
                "item_id": item_id,
                "scope_id": item.scope_id,
                "reviewer": reviewer,
                "assigned_by": assigned_by or reviewer,
                "review_item": item,
            },
        )
        self.store.save(assignment)
        self.store.set_active_for_item(item_id, assignment.assignment_id)

        try:
            self._queue.claim(item_id, reviewer)
        except (ConflictingClaimError, InvalidReviewItemTransitionError, ExpiredReviewItemError):
            pass

        return assignment

    def unassign(self, item_id: str, reviewer: str) -> Assignment:
        """Revoke reviewer's active assignment on item_id.

        Never releases Commit #8's own queue-level claim (Commit #8 has
        no such operation) -- only this service's own assignment record
        is revoked.

        Raises:
            ValueError: If reviewer is missing or blank
            NotAssignedError: If reviewer does not currently hold
                item_id's active assignment
        """
        self._require_text(reviewer, "reviewer")

        current = self._active(item_id)
        if current is None or current.reviewer != reviewer:
            raise NotAssignedError(
                f"reviewer {reviewer!r} does not currently hold an active assignment on item {item_id!r}"
            )

        revoked = replace(current, status=REVOKED, revoked_at=datetime.now(timezone.utc))
        self.store.save(revoked)
        self.store.set_active_for_item(item_id, None)
        return revoked

    def get_assignment(self, item_id: str):
        """item_id's current ACTIVE assignment, or None if it has none
        (never assigned, or its last assignment was revoked)."""
        return self._active(item_id)

    def list_for_reviewer(self, reviewer: str, scope_id: str) -> list:
        """Every assignment (active and revoked alike) ever made to
        reviewer within scope_id, oldest first.

        Raises:
            ValueError: If reviewer or scope_id is missing or blank
        """
        self._require_text(reviewer, "reviewer")
        self._require_text(scope_id, "scope_id")
        return self.store.list_for_reviewer(reviewer, scope_id)

    def history(self, item_id: str) -> list:
        """Every assignment ever made for item_id, oldest first --
        active and revoked alike (see Rules: "Reassignment preserves
        history")."""
        return self.store.list_for_item(item_id)

    def _active(self, item_id: str):
        active_id = self.store.active_for_item(item_id)
        return self.store.get(active_id) if active_id is not None else None

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required and must be non-blank")
