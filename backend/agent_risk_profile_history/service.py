import re
from datetime import datetime

from .in_memory_store import InMemoryRiskProfileHistoryStore
from .models import CHANGE_TYPES, LLMAgentRiskProfileChange
from .store import RiskProfileHistoryStore

# Same secret-detection convention already kept locally by
# backend.agent_policy_history, backend.agent_policy_audit,
# backend.agent_policy_metrics, backend.agent_strategy_decision_audit,
# and backend.llm.tool_audit -- kept local here too rather than
# refactoring any of those.
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
    before/after/reason so a risk profile's own match/reason content can
    never leak a credential into this history trail, the same
    discipline every other audit-adjacent module in this repository
    already applies to its own free-text fields."""
    if isinstance(value, str):
        return "[REDACTED]" if _looks_secret(value) else value
    if isinstance(value, dict):
        return {key: _redact_deep(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_deep(item) for item in value]
    return value


class UnknownRiskProfileChangeError(KeyError):
    """Raised when get() is given a change_id that was never recorded."""


class InvalidRiskProfileChangeError(ValueError):
    """Raised when record_change()/list()/list_for_scope()/get_at() is
    given invalid arguments."""


class LLMAgentRiskProfileHistoryService:
    """Makes meaningful Commit #1 risk profile changes, and Commit #6
    activation/deactivation events, observable after the fact, as one
    append-only, scope-isolated change trail -- not a new event/history
    framework.

    Mirrors backend.agent_policy_history.LLMAgentPolicyHistoryService
    check-for-check: persistence follows the exact save/get/list_for_--
    split that module already uses (an InMemoryRiskProfileHistoryStore
    by default, or the JSON-file-backed store built on the same
    backend.storage.AtomicJsonFile), and before/after/reason content is
    passed through the same secret-redaction convention this repository
    already keeps locally in every comparable module, rather than a
    second detection scheme.

    record_change() never reads or mutates the profile it observes, and
    never decides on its own whether a change happened -- it is a pure
    recorder, called by whichever caller already made the change (see
    backend.agent_risk_profile_history.tracked for the two thin wrappers
    around Commit #1/#6's own services that call this automatically
    through the real lifecycle). Recording a change can therefore never
    itself alter current profile/activation behavior (Rule: "Historical
    reads must not alter current state" -- true for every read here,
    and recording itself is not a read of current state at all).
    """

    def __init__(self, store: RiskProfileHistoryStore = None):
        self.store = store if store is not None else InMemoryRiskProfileHistoryStore()

    def record_change(
        self,
        scope_id: str,
        profile_id: str,
        change_type: str,
        version: int,
        before: dict,
        after: dict,
        actor: str = None,
        reason: str = None,
    ) -> LLMAgentRiskProfileChange:
        """Append one change record.

        Raises:
            InvalidRiskProfileChangeError: If scope_id/profile_id is
                missing, change_type is not one of CHANGE_TYPES, version
                is not a non-negative int, before/after is given and is
                not a dict, or reason is given and is not a string
        """
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskProfileChangeError("scope_id is required")
        if not profile_id or not isinstance(profile_id, str):
            raise InvalidRiskProfileChangeError("profile_id is required")
        if change_type not in CHANGE_TYPES:
            raise InvalidRiskProfileChangeError(f"change_type {change_type!r} is not one of {sorted(CHANGE_TYPES)}")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise InvalidRiskProfileChangeError("version must be a positive integer")
        if before is not None and not isinstance(before, dict):
            raise InvalidRiskProfileChangeError("before must be a dict or None")
        if after is not None and not isinstance(after, dict):
            raise InvalidRiskProfileChangeError("after must be a dict or None")
        if reason is not None and not isinstance(reason, str):
            raise InvalidRiskProfileChangeError("reason must be a string or None")

        change = LLMAgentRiskProfileChange(
            scope_id=scope_id,
            profile_id=profile_id,
            version=version,
            change_type=change_type,
            before=_redact_deep(before),
            after=_redact_deep(after),
            actor=actor,
            reason=_redact_deep(reason),
        )
        return self.store.save(change)

    def get(self, change_id: str) -> LLMAgentRiskProfileChange:
        change = self.store.get(change_id)
        if change is None:
            raise UnknownRiskProfileChangeError(change_id)
        return change

    def list(self, profile_id: str) -> list:
        """Every change recorded for profile_id, oldest first -- the
        complete history, never collapsed to a single latest state."""
        if not profile_id or not isinstance(profile_id, str):
            raise InvalidRiskProfileChangeError("profile_id is required")
        return self.store.list_for_profile(profile_id)

    def list_for_scope(self, scope_id: str) -> list:
        """Every change recorded for scope_id, oldest first -- never
        includes a change from any other scope."""
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRiskProfileChangeError("scope_id is required")
        return self.store.list_for_scope(scope_id)

    def get_at(self, profile_id: str, timestamp: datetime):
        """Reconstruct the applicable snapshot of profile_id as of
        `timestamp`: the `after` snapshot of the latest recorded change
        at or before it.

        Deterministic by construction -- ties at the exact same
        created_at (which list_for_profile() already orders by
        (created_at, change_id)) are broken the same way every time.
        Returns None if profile_id had no recorded change at or before
        `timestamp` (nothing existed yet). Never mutates anything --
        purely a read over already-recorded, immutable history (Rule:
        "Historical reads must not alter current state").

        Raises:
            InvalidRiskProfileChangeError: If profile_id is missing, or
                timestamp is not a datetime
        """
        if not isinstance(timestamp, datetime):
            raise InvalidRiskProfileChangeError("timestamp must be a datetime")

        applicable = [change for change in self.list(profile_id) if change.created_at <= timestamp]
        if not applicable:
            return None
        return applicable[-1].after
