import dataclasses
from datetime import datetime, timezone

from backend.agent_policy_engine import LLMAgentPolicyEvaluator

from .in_memory_store import InMemoryLLMAgentPolicyExceptionStore
from .models import ACTIVE, REVOKED, STATUSES, LLMAgentPolicyException
from .store import LLMAgentPolicyExceptionStore


class UnknownPolicyExceptionError(KeyError):
    """Raised when get()/revoke()/is_active() is given an exception_id
    that was never created."""


class InvalidPolicyExceptionQueryError(ValueError):
    """Raised when list()/applicable() is given an invalid scope_id or status."""


class LLMAgentPolicyExceptionService:
    """Grants explicit, time-bound, narrowly scoped relief from one
    specific Commit #1 policy's denial, without modifying that policy or
    weakening enforcement for anything an exception does not name.

    Reuses the exact model
    backend.session.execution_policy_risk_override.ExecutionPolicyRiskOverrideService
    already established for the repo's other explicit, time-bound
    tolerance, rather than a second authorization framework: create()
    requires a non-blank reason and a non-None expires_at (enforced by
    LLMAgentPolicyException's own __post_init__, mirroring
    ExecutionPolicyRiskOverride's), an exception is active only while its
    status is ACTIVE and it has not passed expires_at, and revoking one
    never deletes its record or its reason -- it flips status to REVOKED
    via save(), the same "never erase, only retire" discipline Commit
    #1's own archive() already uses for a policy record. Persistence
    follows the exact save/get/list_for_scope split
    backend.agent_policy_engine.LLMAgentPolicyService already uses (an
    InMemoryLLMAgentPolicyExceptionStore by default, or the
    JSON-file-backed store built on the same
    backend.storage.AtomicJsonFile).

    applicable() -- used by LLMAgentPolicyExceptionAwareDecisionEngine,
    never by LLMAgentPolicyEvaluator or LLMAgentPolicyDecisionEngine
    themselves, which stay entirely unaware exceptions exist -- reuses
    Commit #1's own LLMAgentPolicyEvaluator._constraints_met() match
    logic rather than a third copy of the same {field: expected}
    condition matching backend.llm.tool_permissions.LLMToolPermissionPolicy
    also already uses. Results are ordered narrowest match first (most
    match keys), so "narrow ... preferred over broad overrides" governs
    which exception is cited as provenance whenever more than one
    applies.
    """

    def __init__(self, store: LLMAgentPolicyExceptionStore = None):
        self.store = store if store is not None else InMemoryLLMAgentPolicyExceptionStore()

    def create(
        self, scope_id: str, policy_id: str, match: dict, reason: str, expires_at: datetime
    ) -> LLMAgentPolicyException:
        """Grant a new, ACTIVE exception.

        Raises:
            InvalidPolicyExceptionError: If scope_id, policy_id, reason,
                or match is missing/blank/invalid, or expires_at is not a
                datetime (propagated from LLMAgentPolicyException's own
                validation, not re-derived here)
        """
        exception = LLMAgentPolicyException(
            scope_id=scope_id, policy_id=policy_id, match=match, reason=reason, expires_at=expires_at,
        )
        return self.store.save(exception)

    def get(self, exception_id: str) -> LLMAgentPolicyException:
        exception = self.store.get(exception_id)
        if exception is None:
            raise UnknownPolicyExceptionError(exception_id)
        return exception

    def list(self, scope_id: str, status: str = None) -> list:
        self._validate_scope_id(scope_id)
        if status is not None:
            self._validate_status(status)
        return self.store.list_for_scope(scope_id, status)

    def revoke(self, exception_id: str) -> LLMAgentPolicyException:
        """Retire exception_id by marking it REVOKED, never by deleting
        it. Idempotent: revoking an already-REVOKED exception simply
        returns it unchanged. Takes effect immediately, even if
        expires_at has not yet passed.

        Raises:
            UnknownPolicyExceptionError: If exception_id was never created
        """
        exception = self.get(exception_id)
        if exception.status == REVOKED:
            return exception
        return self.store.save(dataclasses.replace(exception, status=REVOKED))

    def is_active(self, exception_id: str, now: datetime = None) -> bool:
        """Whether exception_id is currently active: status is ACTIVE
        and expires_at has not passed as of `now` (defaulting to the
        real current time).

        Raises:
            UnknownPolicyExceptionError: If exception_id was never created
        """
        return self._is_active(self.get(exception_id), now)

    def applicable(self, scope_id: str, policy_id: str, action_context: dict, now: datetime = None) -> list:
        """Every currently-active exception in scope_id that grants
        relief from policy_id's denial and whose match constraints hold
        against action_context, narrowest (most match keys) first, tied
        by exception_id for determinism.

        Never crosses a scope boundary: only exceptions whose own
        scope_id is exactly scope_id are ever considered, and only those
        naming this exact policy_id -- an exception is never consulted
        for a policy it was not explicitly granted against.

        Raises:
            InvalidPolicyExceptionQueryError: If scope_id or
                action_context is invalid
        """
        self._validate_scope_id(scope_id)
        if not isinstance(action_context, dict):
            raise InvalidPolicyExceptionQueryError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        candidates = [
            exception
            for exception in self.store.list_for_scope(scope_id, status=ACTIVE)
            if exception.policy_id == policy_id
            and self._is_active(exception, now)
            and LLMAgentPolicyEvaluator._constraints_met(exception.match, action_context)
        ]
        return sorted(candidates, key=lambda exception: (-len(exception.match), exception.exception_id))

    @staticmethod
    def _is_active(exception: LLMAgentPolicyException, now: datetime = None) -> bool:
        if exception.status != ACTIVE:
            return False
        now = now or datetime.now(timezone.utc)
        return exception.expires_at > now

    @staticmethod
    def _validate_scope_id(scope_id):
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidPolicyExceptionQueryError(
                "scope_id is required and must identify a project/notebook/API"
            )

    @staticmethod
    def _validate_status(status):
        if status not in STATUSES:
            raise InvalidPolicyExceptionQueryError(f"status {status!r} is not one of {sorted(STATUSES)}")
