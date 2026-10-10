from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.agent_policy_engine import ALLOW
from backend.storage import AtomicJsonFile

from .evaluation import LLMAgentTaskRecoveryGuardEvaluationService
from .models import ACTIVE, APPROVED, REVOKED, AgentTaskRecoveryPreflightAuthorization
from .preflight_approval import LLMAgentTaskRecoveryPreflightApprovalService
from .preflight_invalidation import LLMAgentTaskRecoveryPreflightInvalidationService
from .preflight_store import LLMAgentTaskRecoveryPreflightStore


class InvalidAgentTaskRecoveryPreflightAuthorizationError(ValueError):
    """Raised when authorize()/get()/is_authorized()/revoke() is given
    invalid arguments, or a preflight is not currently eligible to be
    authorized (not approved, unknown, superseded, invalidated, or
    failing a fresh guard/policy re-evaluation)."""


class AgentTaskRecoveryPreflightAuthorizationStore(ABC):
    """Raw persistence for AgentTaskRecoveryPreflightAuthorization
    records -- indexed both by their own authorization_id (Rule: `get()`
    is looked up this way) and by (task_id, preflight_id) (Rule:
    "authorization is bound to the exact task_id + preflight_id", and
    authorize()'s own idempotency/revoked-reuse checks need this same
    lookup). There is no delete(): a revoked authorization is a fresh
    dataclasses.replace() saved back through the service layer, never
    removed."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflightAuthorization) -> AgentTaskRecoveryPreflightAuthorization:
        ...

    @abstractmethod
    def get(self, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        ...

    @abstractmethod
    def get_for_preflight(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        ...


class InMemoryAgentTaskRecoveryPreflightAuthorizationStore(AgentTaskRecoveryPreflightAuthorizationStore):
    """Stores AgentTaskRecoveryPreflightAuthorization records in memory,
    for development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_preflight: dict = {}

    def save(self, record: AgentTaskRecoveryPreflightAuthorization) -> AgentTaskRecoveryPreflightAuthorization:
        stored = deepcopy(record)
        self._by_id[record.authorization_id] = stored
        self._by_preflight[(record.task_id, record.preflight_id)] = stored
        return deepcopy(stored)

    def get(self, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        record = self._by_id.get(authorization_id)
        return deepcopy(record) if record is not None else None

    def get_for_preflight(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        record = self._by_preflight.get((task_id, preflight_id))
        return deepcopy(record) if record is not None else None


class JsonAgentTaskRecoveryPreflightAuthorizationStore(AgentTaskRecoveryPreflightAuthorizationStore):
    """Persists AgentTaskRecoveryPreflightAuthorization records to a JSON
    file, keyed by their own authorization_id; get_for_preflight() scans
    the (small, one-per-preflight) collection rather than maintaining a
    second on-disk index."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryPreflightAuthorization) -> AgentTaskRecoveryPreflightAuthorization:
        records = self.file.read()
        records[record.authorization_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        records = self.file.read()
        data = records.get(authorization_id)
        return AgentTaskRecoveryPreflightAuthorization.from_dict(data) if data is not None else None

    def get_for_preflight(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        records = self.file.read()
        for data in records.values():
            if data.get("task_id") == task_id and data.get("preflight_id") == preflight_id:
                return AgentTaskRecoveryPreflightAuthorization.from_dict(data)
        return None


class LLMAgentTaskRecoveryPreflightAuthorizationService:
    """Converts one Commit #8-approved preflight into a live execution
    authorization -- the final gate before a caller would ever hand a
    recovery plan to Commit #4(-of-agent_task_event_analytics)'s own
    execution service -- never a new auth/token framework (Rule: "Do not
    invent a new auth/token framework or duplicate existing authorization
    infrastructure"): authorize() only ever reads through Commit #4's own
    preflight store, Commit #6's own invalidation service (itself reusing
    Commit #5's freshness), Commit #8's own approval service, and Commit
    #2's own guard evaluation service -- exactly the same checks this
    whole preceding pipeline already performs, never re-derived a second
    way, plus one small, genuinely new record type for the authorization
    fact itself.

    Never trusts an old approval blindly (Rule: "Re-check preflight
    freshness/usability before authorization"; "Re-check applicable
    recovery guard/policy constraints"): approval (Commit #8) only ever
    proves the preflight WAS safe and ALLOW at approval time. authorize()
    independently re-verifies, right now: the preflight is still task_id's
    own CURRENT stored preflight (never a superseded one), Commit #6's
    own invalidate_if_stale() does not report it invalid, AND a FRESH
    Commit #2 evaluate() call against the preflight's own embedded plan
    still returns ALLOW -- never merely trusting the preflight's own
    stored `.decision` field, which was computed at preflight time and
    could theoretically have gone stale in a way freshness's own narrower
    comparisons do not happen to catch.

    Authorization only ever succeeds for an explicitly APPROVED preflight
    (Rule: "Authorization only succeeds for an explicitly approved
    preflight"): authorize() requires Commit #8's own
    LLMAgentTaskRecoveryPreflightApprovalService.get() to report status
    APPROVED before doing anything else -- a PENDING or REJECTED preflight
    is refused immediately, without even reaching the freshness/guard
    checks.

    Bound to the EXACT (task_id, preflight_id) (Rule): a later
    preflight_id for the same task_id (e.g. one Commit #7's own
    revalidate() produces) is a wholly separate authorization subject
    with no record of its own yet -- querying is_authorized() for an
    OLDER, now-superseded preflight_id returns False even though its own
    stored record's `status` field still honestly says "active" (Rule:
    "A superseded ... preflight invalidates its authorization" -- the
    STORED historical fact is never rewritten, only what counts as
    "currently usable" is reassessed against Commit #4's own current
    preflight pointer).

    authorize() is idempotent for an already-ACTIVE authorization of the
    exact same preflight_id (Rule: "Repeated authorization of the same
    still-valid approved preflight should be deterministic/idempotent") --
    returns the existing record unchanged, never minting a second one.
    A REVOKED authorization for that exact preflight_id can never be
    reused (Rule: "Revoked authorizations can never be reused") -- a
    fresh authorize() call for it raises rather than silently minting a
    replacement; a genuinely new situation needs a genuinely new
    preflight_id (via Commit #7's own revalidate()) to ever be authorized
    again, the same "terminal once decided" boundary Commit #8's own
    rejected-preflight rule already establishes for approval.

    Never executes recovery, never mutates task state (Rule): nothing in
    this class calls anything from Commit #4(-of-agent_task_event_
    analytics)'s own execution service, or any lifecycle/queue/dead-letter
    mutation -- this class only ever establishes or reads authorization
    STATE for a preflight_id.

    Persists using this package's own established conventions (Rule):
    the same AgentTaskRecoveryPreflightApprovalStore-shaped ABC +
    InMemory/Json trio Commit #8 already establishes, applied here to a
    slightly richer dual-indexed (by authorization_id, and by (task_id,
    preflight_id)) shape since get() and authorize()/is_authorized() each
    need a different lookup key.
    """

    def __init__(
        self,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        approval_service: LLMAgentTaskRecoveryPreflightApprovalService = None,
        invalidation_service: LLMAgentTaskRecoveryPreflightInvalidationService = None,
        evaluation_service: LLMAgentTaskRecoveryGuardEvaluationService = None,
        store: AgentTaskRecoveryPreflightAuthorizationStore = None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._invalidation_service = (
            invalidation_service
            if invalidation_service is not None
            else LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=self._preflight_store)
        )
        self._approval_service = (
            approval_service
            if approval_service is not None
            else LLMAgentTaskRecoveryPreflightApprovalService(
                preflight_store=self._preflight_store, invalidation_service=self._invalidation_service
            )
        )
        self._evaluation_service = (
            evaluation_service if evaluation_service is not None else LLMAgentTaskRecoveryGuardEvaluationService()
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightAuthorizationStore()

    def authorize(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightAuthorization:
        """Convert task_id's exact, Commit #8-approved preflight_id into
        a live execution authorization. Idempotent when already active;
        raises for a revoked one.

        Raises:
            InvalidAgentTaskRecoveryPreflightAuthorizationError: If
                task_id/preflight_id is not a non-empty string, the
                preflight_id's own authorization was already revoked, it
                has not been APPROVED (Commit #8), it names no recorded
                preflight, it is no longer task_id's current stored
                preflight, Commit #6's own invalidate_if_stale() reports
                it invalid, or a fresh Commit #2 evaluation no longer
                returns ALLOW
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

        existing = self._store.get_for_preflight(task_id, preflight_id)
        if existing is not None:
            if existing.status == REVOKED:
                raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                    f"authorization for preflight {preflight_id!r} was revoked and cannot be reused"
                )
            return existing

        approval = self._approval_service.get(task_id, preflight_id)
        if approval is None or approval.status != APPROVED:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"preflight {preflight_id!r} has not been approved and cannot be authorized"
            )

        preflight = self._require_preflight(task_id, preflight_id)
        self._verify_current_and_valid(task_id, preflight_id)
        self._verify_guard(task_id, preflight)

        authorization = AgentTaskRecoveryPreflightAuthorization(
            task_id=task_id, preflight_id=preflight_id, approval_id=approval.approval_id,
            status=ACTIVE, revocation_reason=None, created_at=datetime.now(timezone.utc), revoked_at=None,
        )
        return self._store.save(authorization)

    def get(self, task_id: str, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightAuthorization]:
        """task_id's authorization record for its exact authorization_id,
        or None if it does not exist or belongs to a different task_id --
        never raises for a missing record.

        Raises:
            InvalidAgentTaskRecoveryPreflightAuthorizationError: If
                task_id or authorization_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")

        record = self._store.get(authorization_id)
        if record is None or record.task_id != task_id:
            return None
        return record

    def is_authorized(self, task_id: str, preflight_id: str) -> bool:
        """Whether task_id's exact preflight_id currently has a live
        (active, and still task_id's own current stored preflight)
        authorization -- a cheap status read, never re-checking
        invalidation or guard/policy constraints (Commit #10's own,
        deeper job).

        Raises:
            InvalidAgentTaskRecoveryPreflightAuthorizationError: If
                task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

        record = self._store.get_for_preflight(task_id, preflight_id)
        if record is None or record.status != ACTIVE:
            return False

        current = self._preflight_store.get(task_id)
        return current is not None and current.preflight_id == preflight_id

    def revoke(self, task_id: str, authorization_id: str, reason: str) -> AgentTaskRecoveryPreflightAuthorization:
        """Revoke task_id's exact authorization_id. Idempotent when
        already revoked (the first recorded reason stands).

        Raises:
            InvalidAgentTaskRecoveryPreflightAuthorizationError: If
                task_id/authorization_id/reason is not a non-empty
                string, or authorization_id names no recorded
                authorization for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")
        self._require_text(reason, "reason")

        record = self.get(task_id, authorization_id)
        if record is None:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"no authorization {authorization_id!r} is recorded for task_id {task_id!r}"
            )
        if record.status == REVOKED:
            return record

        resolved = replace(record, status=REVOKED, revocation_reason=reason, revoked_at=datetime.now(timezone.utc))
        return self._store.save(resolved)

    def _verify_current_and_valid(self, task_id: str, preflight_id: str) -> None:
        current = self._preflight_store.get(task_id)
        if current is None or current.preflight_id != preflight_id:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"preflight {preflight_id!r} has been superseded by a newer preflight for task_id {task_id!r}"
            )

        invalidation = self._invalidation_service.invalidate_if_stale(task_id)
        if invalidation.is_invalid:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"preflight {preflight_id!r} is no longer valid: {invalidation.reason}"
            )

    def _verify_guard(self, task_id: str, preflight) -> None:
        if preflight.plan is None:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"preflight {preflight.preflight_id!r} has no recovery plan and cannot be authorized"
            )

        evaluation = self._evaluation_service.evaluate(task_id, preflight.plan)
        if evaluation.decision != ALLOW:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"current recovery guard/policy evaluation for preflight {preflight.preflight_id!r} is "
                f"{evaluation.decision!r}, not {ALLOW!r}: {evaluation.reason}"
            )

    def _require_preflight(self, task_id: str, preflight_id: str):
        preflight = next(
            (record for record in self._preflight_store.history(task_id) if record.preflight_id == preflight_id),
            None,
        )
        if preflight is None:
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"no preflight {preflight_id!r} is recorded for task_id {task_id!r}"
            )
        return preflight

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightAuthorizationError(
                f"{field_name} is required and must be a non-empty string"
            )
