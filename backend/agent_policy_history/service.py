import re
from datetime import datetime

from .in_memory_store import InMemoryLLMAgentPolicyHistoryStore
from .models import CHANGE_TYPES, LLMAgentPolicyChange
from .store import LLMAgentPolicyHistoryStore

# Same secret-detection convention already kept locally by
# backend.agent_policy_audit, backend.agent_policy_metrics,
# backend.agent_strategy_decision_audit, and backend.llm.tool_audit --
# kept local here too rather than refactoring any of those.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _redact_deep(value):
    """value, with every secret-looking string replaced by "[REDACTED]",
    walking dicts and lists recursively -- non-string, non-container
    values (bools, numbers, None) pass through unchanged. Applied to
    before/after so a rule's own match/reason content can never leak a
    credential into this history trail, the same discipline every other
    audit-adjacent module in this repository already applies to its own
    free-text fields."""
    if isinstance(value, str):
        return "[REDACTED]" if _looks_secret(value) else value
    if isinstance(value, dict):
        return {key: _redact_deep(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_deep(item) for item in value]
    return value


class UnknownPolicyChangeError(KeyError):
    """Raised when get() is given a change_id that was never recorded."""


class InvalidPolicyChangeError(ValueError):
    """Raised when record_change()/list()/list_for_scope()/get_at() is
    given invalid arguments."""


class LLMAgentPolicyHistoryService:
    """Makes meaningful Commit #1 policy and Commit #5 exception changes
    observable after the fact, as one append-only, scope-isolated change
    trail -- not a new event/history framework.

    Persistence follows the exact save/get/list_for_-- split every other
    audit-shaped module in this series already uses (an
    InMemoryLLMAgentPolicyHistoryStore by default, or the JSON-file-backed
    store built on the same backend.storage.AtomicJsonFile), and
    before/after content is passed through the same secret-redaction
    convention this repository already keeps locally in every comparable
    module, rather than a second detection scheme.

    record_change() never reads or mutates the policy/exception it
    observes, and never decides on its own whether a change happened --
    it is a pure recorder, called by whichever caller already made the
    change (see backend.agent_policy_history.tracked for the two thin
    wrappers around Commit #1/#5's own services that call this
    automatically). Recording a change can therefore never itself alter
    current policy behavior.
    """

    def __init__(self, store: LLMAgentPolicyHistoryStore = None):
        self.store = store if store is not None else InMemoryLLMAgentPolicyHistoryStore()

    def record_change(
        self,
        scope_id: str,
        policy_id: str,
        change_type: str,
        before: dict,
        after: dict,
        actor: str = None,
        reason: str = None,
    ) -> LLMAgentPolicyChange:
        """Append one change record.

        Raises:
            InvalidPolicyChangeError: If scope_id/policy_id is missing,
                change_type is not one of CHANGE_TYPES, before/after is
                given and is not a dict, or reason is given and is not a
                string
        """
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidPolicyChangeError("scope_id is required")
        if not policy_id or not isinstance(policy_id, str):
            raise InvalidPolicyChangeError("policy_id is required")
        if change_type not in CHANGE_TYPES:
            raise InvalidPolicyChangeError(f"change_type {change_type!r} is not one of {sorted(CHANGE_TYPES)}")
        if before is not None and not isinstance(before, dict):
            raise InvalidPolicyChangeError("before must be a dict or None")
        if after is not None and not isinstance(after, dict):
            raise InvalidPolicyChangeError("after must be a dict or None")
        if reason is not None and not isinstance(reason, str):
            raise InvalidPolicyChangeError("reason must be a string or None")

        change = LLMAgentPolicyChange(
            scope_id=scope_id,
            policy_id=policy_id,
            change_type=change_type,
            before=_redact_deep(before),
            after=_redact_deep(after),
            actor=actor,
            reason=_redact_deep(reason),
        )
        return self.store.save(change)

    def get(self, change_id: str) -> LLMAgentPolicyChange:
        change = self.store.get(change_id)
        if change is None:
            raise UnknownPolicyChangeError(change_id)
        return change

    def list(self, policy_id: str) -> list:
        """Every change recorded for policy_id, oldest first -- the
        complete history, never collapsed to a single latest state."""
        if not policy_id or not isinstance(policy_id, str):
            raise InvalidPolicyChangeError("policy_id is required")
        return self.store.list_for_policy(policy_id)

    def list_for_scope(self, scope_id: str) -> list:
        """Every change recorded for scope_id, oldest first -- never
        includes a change from any other scope."""
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidPolicyChangeError("scope_id is required")
        return self.store.list_for_scope(scope_id)

    def get_at(self, policy_id: str, timestamp: datetime):
        """Reconstruct the applicable version of policy_id as of
        `timestamp`: the `after` snapshot of the latest recorded change
        at or before it.

        Deterministic by construction -- ties at the exact same
        created_at (which list_for_policy() already orders by
        (created_at, change_id)) are broken the same way every time.
        Returns None if policy_id had no recorded change at or before
        `timestamp` (nothing existed yet).

        Raises:
            InvalidPolicyChangeError: If policy_id is missing, or
                timestamp is not a datetime
        """
        if not isinstance(timestamp, datetime):
            raise InvalidPolicyChangeError("timestamp must be a datetime")

        applicable = [change for change in self.list(policy_id) if change.created_at <= timestamp]
        if not applicable:
            return None
        return applicable[-1].after
