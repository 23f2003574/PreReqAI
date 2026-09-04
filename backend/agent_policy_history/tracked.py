from backend.agent_policy_engine import ACTIVE, LLMAgentPolicyService
from backend.agent_policy_exceptions import LLMAgentPolicyExceptionService

from .models import ARCHIVED, CREATED, EXCEPTION_CREATED, EXCEPTION_REVOKED, UPDATED
from .service import LLMAgentPolicyHistoryService

# Fields save() always changes regardless of whether anything a caller
# actually asked to change did -- comparing raw to_dict() snapshots
# without excluding these would make every update()/archive() call look
# "meaningful" even when it truly changed nothing (see Rules: "Track
# meaningful ... changes").
_VOLATILE_FIELDS = ("updated_at",)


def _without_volatile_fields(snapshot: dict) -> dict:
    return {key: value for key, value in snapshot.items() if key not in _VOLATILE_FIELDS}


def _meaningfully_different(before: dict, after: dict) -> bool:
    if before is None or after is None:
        return before != after
    return _without_volatile_fields(before) != _without_volatile_fields(after)


class LLMAgentPolicyHistoryTrackedService(LLMAgentPolicyService):
    """Commit #1's LLMAgentPolicyService, unchanged, with exactly one
    more step after create()/update()/archive() succeeds: recording a
    Commit #10 LLMAgentPolicyChange for it.

    Not a second policy service, and Commit #1 is never modified:
    every method here delegates the entire operation to
    super().create()/update()/archive() first, completely unchanged, and
    only afterward records what happened. A read (get()/list()) is never
    wrapped, since nothing about a read is ever a change to track.

    Recording is best-effort: a failure in the history store can never
    surface to the caller or undo an already-applied policy change --
    "do not alter current policy behavior" holds by construction, since
    the real create()/update()/archive() call has already fully
    completed, successfully, by the time any history code runs.

    update()/archive() only record when the resulting snapshot actually
    differs from the one immediately before it (excluding the always-
    changing updated_at) -- an idempotent archive() of an
    already-ARCHIVED policy, or an update() that changed nothing,
    produces no new history entry, per "track *meaningful* changes".
    create() always records: a brand-new policy is inherently a
    meaningful change.
    """

    def __init__(self, store=None, history_service: LLMAgentPolicyHistoryService = None, actor: str = None):
        super().__init__(store)
        self._history_service = history_service if history_service is not None else LLMAgentPolicyHistoryService()
        self._actor = actor

    def _safe_record(self, scope_id, policy_id, change_type, before, after) -> None:
        try:
            self._history_service.record_change(scope_id, policy_id, change_type, before, after, actor=self._actor)
        except Exception:
            pass

    def create(self, scope_id, name, rules, status=ACTIVE):
        policy = super().create(scope_id, name, rules, status)
        self._safe_record(policy.scope_id, policy.policy_id, CREATED, before=None, after=policy.to_dict())
        return policy

    def update(self, policy_id, name=None, rules=None):
        before = self.get(policy_id).to_dict()
        policy = super().update(policy_id, name=name, rules=rules)
        after = policy.to_dict()
        if _meaningfully_different(before, after):
            self._safe_record(policy.scope_id, policy_id, UPDATED, before=before, after=after)
        return policy

    def archive(self, policy_id):
        before = self.get(policy_id).to_dict()
        policy = super().archive(policy_id)
        after = policy.to_dict()
        if _meaningfully_different(before, after):
            self._safe_record(policy.scope_id, policy_id, ARCHIVED, before=before, after=after)
        return policy


class LLMAgentPolicyExceptionHistoryTrackedService(LLMAgentPolicyExceptionService):
    """Commit #5's LLMAgentPolicyExceptionService, unchanged, with
    exactly one more step after create()/revoke() succeeds: recording a
    Commit #10 LLMAgentPolicyChange for it, the same "delegate first,
    then record, best-effort" shape LLMAgentPolicyHistoryTrackedService
    already uses for Commit #1.
    """

    def __init__(self, store=None, history_service: LLMAgentPolicyHistoryService = None, actor: str = None):
        super().__init__(store)
        self._history_service = history_service if history_service is not None else LLMAgentPolicyHistoryService()
        self._actor = actor

    def _safe_record(self, scope_id, policy_id, change_type, before, after) -> None:
        try:
            self._history_service.record_change(scope_id, policy_id, change_type, before, after, actor=self._actor)
        except Exception:
            pass

    def create(self, scope_id, policy_id, match, reason, expires_at):
        exception = super().create(scope_id, policy_id, match, reason, expires_at)
        self._safe_record(scope_id, policy_id, EXCEPTION_CREATED, before=None, after=exception.to_dict())
        return exception

    def revoke(self, exception_id):
        before = self.get(exception_id).to_dict()
        exception = super().revoke(exception_id)
        after = exception.to_dict()
        if _meaningfully_different(before, after):
            self._safe_record(exception.scope_id, exception.policy_id, EXCEPTION_REVOKED, before=before, after=after)
        return exception
