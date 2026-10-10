from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.agent_policy_engine import ALLOW
from backend.storage import AtomicJsonFile

from .models import APPROVED, PENDING, REJECTED, AgentTaskRecoveryPreflightApproval
from .preflight_invalidation import LLMAgentTaskRecoveryPreflightInvalidationService
from .preflight_store import LLMAgentTaskRecoveryPreflightStore


class InvalidAgentTaskRecoveryPreflightApprovalError(ValueError):
    """Raised when request()/approve()/reject()/get()/status() is given
    invalid arguments, or a preflight is not currently eligible for the
    requested transition (unknown, not ALLOW, superseded, invalidated,
    or a conflicting approve/reject on an already-opposite-resolved
    record)."""


class AgentTaskRecoveryPreflightApprovalStore(ABC):
    """Raw persistence for the one current AgentTaskRecoveryPreflightApproval
    record per (task_id, preflight_id) -- the same single-current-record-
    per-key shape backend.agent_task_queue_dead_letter.DeadLetterStore and
    this same package's own Commit #6
    AgentTaskRecoveryPreflightInvalidationStore already use for a
    comparable "one durable fact about a specific thing" case. There is
    no update() or delete(): once (task_id, preflight_id) has an approval
    record, it is only ever replaced via dataclasses.replace() through
    the service layer, never rewritten out from under its own history."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflightApproval) -> AgentTaskRecoveryPreflightApproval:
        ...

    @abstractmethod
    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightApproval]:
        ...


class InMemoryAgentTaskRecoveryPreflightApprovalStore(AgentTaskRecoveryPreflightApprovalStore):
    """Stores AgentTaskRecoveryPreflightApproval records in memory, for
    development and testing."""

    def __init__(self):
        self._records: dict = {}

    def save(self, record: AgentTaskRecoveryPreflightApproval) -> AgentTaskRecoveryPreflightApproval:
        stored = deepcopy(record)
        self._records[(record.task_id, record.preflight_id)] = stored
        return deepcopy(stored)

    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightApproval]:
        record = self._records.get((task_id, preflight_id))
        return deepcopy(record) if record is not None else None


class JsonAgentTaskRecoveryPreflightApprovalStore(AgentTaskRecoveryPreflightApprovalStore):
    """Persists AgentTaskRecoveryPreflightApproval records to a JSON
    file, keyed by "task_id::preflight_id"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, preflight_id: str) -> str:
        return f"{task_id}::{preflight_id}"

    def save(self, record: AgentTaskRecoveryPreflightApproval) -> AgentTaskRecoveryPreflightApproval:
        records = self.file.read()
        records[self._key(record.task_id, record.preflight_id)] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightApproval]:
        records = self.file.read()
        data = records.get(self._key(task_id, preflight_id))
        return AgentTaskRecoveryPreflightApproval.from_dict(data) if data is not None else None


class LLMAgentTaskRecoveryPreflightApprovalService:
    """An explicit human approval lifecycle for one specific, persisted
    Commit #4 preflight, before it is ever handed to Commit #4(-of-
    agent_task_event_analytics)'s own recovery execution -- never a
    second generic approval framework (Rule: "Do not invent a second
    generic approval framework or infrastructure"): modeled directly on
    backend.agent_policy_risk_approval.ApprovalRequirement/
    LLMAgentRiskApprovalGate and backend.agent_risk_profile_approval.
    RiskProfileApproval/LLMAgentRiskProfileApprovalService's own PENDING/
    APPROVED/REJECTED vocabulary and "terminal once decided,
    dataclasses.replace()-not-mutate" discipline -- a THIRD from-scratch,
    same-shape reimplementation of that same shape (this repository's own
    established precedent for reusing an approval vocabulary across
    unrelated domains), never a cross-module import of either class,
    since both are permanently keyed to a different subject entirely (one
    RiskDecision/action_context, one profile/version/scope triple) than
    this domain's own (task_id, preflight_id).

    Not a parallel validation/policy layer (Rule: "reuse existing
    approval/gate, actor, persistence, task-state, and policy
    abstractions wherever they already exist"): request()/approve() only
    ever READ through Commit #4's own LLMAgentTaskRecoveryPreflightStore
    and Commit #6's own LLMAgentTaskRecoveryPreflightInvalidationService
    (itself reusing Commit #5's freshness check internally) -- exactly
    the same checks this whole preceding pipeline already performs,
    never re-derived a second way. No approval-policy-enforcement
    abstraction (who may approve, under what authority) was found
    anywhere in this repository scoped to a task_id -- backend.
    agent_policy_risk_approval/agent_risk_profile_approval both accept an
    optional `authorized` callable for exactly this, and this service
    mirrors that same extension point rather than inventing role/permission
    logic of its own (Rule: "Do not duplicate authentication/
    authorization logic").

    Approval never executes recovery (Rule): nothing in this class calls
    anything from Commit #4(-of-agent_task_event_analytics)'s own
    execution service, or Commit #3(-of-this-series)'s own preflight/
    guard pipeline beyond the read-only checks above -- this class only
    ever establishes or reads approval STATE for a preflight_id.

    Approval is tied to the EXACT preflight_id (Rule: "Approval applies
    to a specific persisted preflight ID"): a later preflight_id for the
    SAME task_id (e.g. one Commit #7's own revalidate() produces) is a
    wholly separate approval subject with no record of its own yet --
    "revalidated replacement requires its own approval" holds structurally,
    not by a documented promise, since nothing here ever looks up an
    approval by task_id alone.

    request()/approve() both verify the preflight is current and usable
    before proceeding (Rule): decision must be backend.agent_policy_engine.
    ALLOW (Rule: "Only an executable/allowed preflight may become
    approved" -- covers "incompatible" preflights too, since a DENY/REVIEW
    decision is exactly incompatible with approval), it must still be
    task_id's own CURRENT stored preflight (Commit #4's own get(), never
    an older, superseded one), and Commit #6's own invalidate_if_stale()
    must not report it invalid (covers "stale"/"invalidated" together,
    reusing Commit #5's freshness internally with no duplicated logic of
    its own). approve() re-verifies all three at DECISION time, not only
    at request() time, since real time may have passed between the two
    and conditions can change in between.

    reject() deliberately skips all of the above (Rule is silent on
    requiring it, and rejecting an already-bad preflight is always safe):
    rejecting is how a caller disposes of a preflight regardless of why
    it should not be used, so it never needs the preflight to still be
    current, allowed, or valid.

    request() is idempotent by (task_id, preflight_id) existence, in ANY
    status -- not merely "still pending" (Rule: "Rejected preflights
    cannot be approved without creating/revalidating against a new
    current preflight" -- allowing a fresh PENDING request to reopen an
    already-REJECTED preflight_id would silently defeat that exact
    rule): once a request exists for an exact preflight_id, in whatever
    state, calling request() again simply returns it unchanged.

    approve()/reject() are idempotent for a record ALREADY in the
    requested state (Rule: "idempotent where existing state already
    represents the requested transition") -- a deliberate divergence from
    BOTH named precedents (which raise for any non-PENDING transition
    attempt at all), made because this commit's own Rules explicitly ask
    for it. A record in the OPPOSITE resolved state still raises: reusing
    a rejected record's approve() call (or an approved record's reject())
    is a genuine conflicting transition, never "already represents it".

    Preserves approval history (Rule: "Preserve approval history; never
    overwrite prior decisions"): every transition is a fresh
    dataclasses.replace() saved back to the store, and get()/status()
    always report the CURRENT, single authoritative record for a
    preflight_id -- there is no update()/delete() capable of losing a
    prior decision's own actor/reason/timestamp, since every one of
    those fields is carried forward by replace() rather than reset.
    """

    def __init__(
        self,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        invalidation_service: LLMAgentTaskRecoveryPreflightInvalidationService = None,
        store: AgentTaskRecoveryPreflightApprovalStore = None,
        authorized=None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._invalidation_service = (
            invalidation_service
            if invalidation_service is not None
            else LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=self._preflight_store)
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightApprovalStore()
        self._authorized = authorized

    def request(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightApproval:
        """Request approval for task_id's exact preflight_id. Idempotent:
        an approval already on record for this exact (task_id,
        preflight_id) -- pending, approved, or rejected -- is returned
        unchanged, never re-requested.

        Raises:
            InvalidAgentTaskRecoveryPreflightApprovalError: If task_id/
                preflight_id is not a non-empty string, preflight_id
                names no recorded preflight at all, its own decision is
                not ALLOW, it is no longer task_id's current stored
                preflight, or Commit #6's own invalidate_if_stale()
                reports it invalid
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

        existing = self._store.get(task_id, preflight_id)
        if existing is not None:
            return existing

        self._verify_approvable(task_id, preflight_id)

        approval = AgentTaskRecoveryPreflightApproval(
            task_id=task_id, preflight_id=preflight_id, status=PENDING,
            actor=None, reason=None, created_at=datetime.now(timezone.utc), resolved_at=None,
        )
        return self._store.save(approval)

    def approve(self, task_id: str, preflight_id: str, actor: str) -> AgentTaskRecoveryPreflightApproval:
        """Approve task_id's exact preflight_id. Idempotent when already
        approved; raises for a REJECTED record (Rule: "Rejected
        preflights cannot be approved without creating/revalidating
        against a new current preflight").

        Raises:
            InvalidAgentTaskRecoveryPreflightApprovalError: If task_id/
                preflight_id/actor is not a non-empty string, no
                request() was ever made for this exact preflight_id, the
                record is REJECTED, `authorized` (if configured) rejects
                actor, or the preflight is no longer current/allowed/
                valid (re-verified at decision time)
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        self._require_text(actor, "actor")

        approval = self._require_approval(task_id, preflight_id)
        if approval.status == APPROVED:
            return approval
        if approval.status == REJECTED:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"preflight {preflight_id!r} was already rejected and cannot be approved; "
                "revalidate and request approval for a new current preflight instead"
            )

        self._verify_approvable(task_id, preflight_id)
        self._check_authorized(actor, task_id)

        resolved = replace(approval, status=APPROVED, actor=actor, resolved_at=datetime.now(timezone.utc))
        return self._store.save(resolved)

    def reject(self, task_id: str, preflight_id: str, actor: str, reason: str) -> AgentTaskRecoveryPreflightApproval:
        """Reject task_id's exact preflight_id. Idempotent when already
        rejected (the first recorded reason/actor stand, never
        overwritten); raises for an APPROVED record.

        Raises:
            InvalidAgentTaskRecoveryPreflightApprovalError: If task_id/
                preflight_id/actor/reason is not a non-empty string, no
                request() was ever made for this exact preflight_id, the
                record is APPROVED, or `authorized` (if configured)
                rejects actor
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        self._require_text(actor, "actor")
        self._require_text(reason, "reason")

        approval = self._require_approval(task_id, preflight_id)
        if approval.status == REJECTED:
            return approval
        if approval.status == APPROVED:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"preflight {preflight_id!r} was already approved and cannot be rejected"
            )

        self._check_authorized(actor, task_id)

        resolved = replace(approval, status=REJECTED, actor=actor, reason=reason, resolved_at=datetime.now(timezone.utc))
        return self._store.save(resolved)

    def get(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightApproval]:
        """task_id's approval record for its exact preflight_id, or None
        if request() was never called for it -- never raises for a
        missing record, the same tolerant-read discipline every other
        read path in this series already establishes.

        Raises:
            InvalidAgentTaskRecoveryPreflightApprovalError: If task_id or
                preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        return self._store.get(task_id, preflight_id)

    def status(self, task_id: str, preflight_id: str) -> Optional[str]:
        """task_id's exact preflight_id's current status (pending/
        approved/rejected), or None if request() was never called for
        it."""
        approval = self.get(task_id, preflight_id)
        return approval.status if approval is not None else None

    def _verify_approvable(self, task_id: str, preflight_id: str) -> None:
        preflight = self._require_preflight(task_id, preflight_id)

        if preflight.decision != ALLOW:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"preflight {preflight_id!r} is {preflight.decision!r}, not {ALLOW!r}, "
                "and is not eligible for approval"
            )

        current = self._preflight_store.get(task_id)
        if current is None or current.preflight_id != preflight_id:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"preflight {preflight_id!r} has been superseded by a newer preflight for task_id {task_id!r}"
            )

        invalidation = self._invalidation_service.invalidate_if_stale(task_id)
        if invalidation.is_invalid:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"preflight {preflight_id!r} is no longer valid: {invalidation.reason}"
            )

    def _require_preflight(self, task_id: str, preflight_id: str):
        preflight = next(
            (record for record in self._preflight_store.history(task_id) if record.preflight_id == preflight_id),
            None,
        )
        if preflight is None:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"no preflight {preflight_id!r} is recorded for task_id {task_id!r}"
            )
        return preflight

    def _require_approval(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightApproval:
        approval = self._store.get(task_id, preflight_id)
        if approval is None:
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"no approval has been requested for preflight {preflight_id!r} of task_id {task_id!r}"
            )
        return approval

    def _check_authorized(self, actor: str, task_id: str) -> None:
        if self._authorized is not None and not self._authorized(actor, task_id):
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"actor {actor!r} is not authorized to decide approvals for task_id {task_id!r}"
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightApprovalError(
                f"{field_name} is required and must be a non-empty string"
            )
