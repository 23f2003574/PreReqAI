import re
from datetime import datetime

from backend.agent_policy_risk_approval import APPROVED, REJECTED
from backend.agent_policy_risk_assessment import LEVELS
from backend.agent_policy_risk_review_queue import (
    CLAIMED,
    EXPIRED,
    PENDING,
    RESOLVED,
    STATUSES,
    LLMAgentRiskReviewQueue,
)

from .models import ReviewMetrics

# Same secret-detection convention already kept locally by
# backend.agent_policy_metrics, backend.llm.security_metrics,
# backend.agent_policy_audit, and every other module in this repository
# that needs it -- kept local here too rather than refactoring any of
# those into a shared one.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)

_OUTCOMES = (APPROVED, REJECTED)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


class SecretInScopeError(ValueError):
    """Raised when a scope_id looks like it carries a credential."""


class InvalidMetricsFilterError(ValueError):
    """Raised when filters is malformed."""


class LLMAgentRiskReviewMetrics:
    """Read-only aggregate metrics over Commit #8's own review queue --
    no new observability system, no new stored aggregate.

    Mirrors backend.agent_policy_metrics.LLMAgentPolicyMetricsService
    (itself mirroring backend.llm.security_metrics.
    LLMSecurityMetricsService) exactly: the queue's own list() is the
    sole source of truth (never a second store, never duplicated
    aggregate state -- see Rules: "Do not persist duplicate aggregate
    state unless existing infrastructure requires it" -- it doesn't
    here), an unrecognized or empty scope yields a clean, zero-valued
    ReviewMetrics rather than an error (see Rules: "Handle empty
    datasets"), and every count is a pure read -- summarize() never
    writes anything and never calls claim()/complete()/enqueue().

    Reads through Commit #8's own list(scope_id) (never the raw store
    directly), so by_status/by_risk_level etc. always reflect the same
    lazily-computed effective status (PENDING/CLAIMED/RESOLVED/EXPIRED)
    every other caller of the queue already sees -- an item whose
    deadline has lapsed is counted as EXPIRED here the instant this
    method is called, exactly as Commit #7's own expiration discipline
    already established, without this service re-deriving that logic
    itself.

    Never touches action_context or decision.reasons/provenance --
    only status, decision.risk_level, resolution["outcome"], claimed_by/
    resolved_by, and the three timestamps are ever read, so a reviewed
    action's own arguments/payload can never leak into a metrics
    snapshot (see Rules: "Do not expose sensitive action payloads").
    The one string a caller controls directly, scope_id, is checked
    against the same secret-detection convention this whole series
    already keeps locally.
    """

    def __init__(self, queue: LLMAgentRiskReviewQueue):
        self._queue = queue

    @staticmethod
    def _require_safe_scope(scope_id) -> None:
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("scope_id is required")
        if _looks_secret(scope_id):
            raise SecretInScopeError(f"scope_id {scope_id!r} looks like it carries a credential")

    @staticmethod
    def _validate_filters(filters) -> dict:
        if filters is None:
            return {}
        if not isinstance(filters, dict):
            raise InvalidMetricsFilterError("filters must be a dict when given")

        start = filters.get("start")
        end = filters.get("end")
        if start is not None and not isinstance(start, datetime):
            raise InvalidMetricsFilterError("filters['start'] must be a datetime")
        if end is not None and not isinstance(end, datetime):
            raise InvalidMetricsFilterError("filters['end'] must be a datetime")
        if start is not None and end is not None and start > end:
            raise InvalidMetricsFilterError("filters['start'] must not be after filters['end']")

        status = filters.get("status")
        if status is not None and status not in STATUSES:
            raise InvalidMetricsFilterError(f"filters['status'] must be one of {STATUSES}")

        risk_level = filters.get("risk_level")
        if risk_level is not None and risk_level not in LEVELS:
            raise InvalidMetricsFilterError(f"filters['risk_level'] must be one of {LEVELS}")

        reviewer = filters.get("reviewer")
        if reviewer is not None and not isinstance(reviewer, str):
            raise InvalidMetricsFilterError("filters['reviewer'] must be a string")

        return filters

    def _matching_items(self, scope_id: str, filters) -> list:
        self._require_safe_scope(scope_id)
        filters = self._validate_filters(filters)

        start = filters.get("start")
        end = filters.get("end")
        status = filters.get("status")
        risk_level = filters.get("risk_level")
        reviewer = filters.get("reviewer")

        matching = []
        for item in self._queue.list(scope_id):
            if start is not None and item.created_at < start:
                continue
            if end is not None and item.created_at > end:
                continue
            if status is not None and item.status != status:
                continue
            if risk_level is not None and item.decision.risk_level != risk_level:
                continue
            if reviewer is not None and reviewer not in (item.claimed_by, item.resolved_by):
                continue
            matching.append(item)
        return matching

    def summarize(self, scope_id: str, filters: dict = None) -> ReviewMetrics:
        """Aggregate every Commit #8 review item for scope_id (narrowed
        by `filters`, when given) into one ReviewMetrics snapshot.

        filters, all optional and combined with AND: start/end (datetime
        bounds on created_at, inclusive), status (one of Commit #8's own
        STATUSES), risk_level (one of Commit #1's own LEVELS), reviewer
        (matches either claimed_by or resolved_by).

        Raises:
            ValueError: If scope_id is missing
            SecretInScopeError: If scope_id looks like it carries a
                credential
            InvalidMetricsFilterError: If filters is malformed
        """
        items = self._matching_items(scope_id, filters)

        by_status = {status: 0 for status in STATUSES}
        by_outcome = {outcome: 0 for outcome in _OUTCOMES}
        by_risk_level = {level: 0 for level in LEVELS}
        reviewer_workload: dict = {}
        stuck_items: list = []
        resolution_seconds_total = 0.0
        resolved_count = 0

        for item in items:
            by_status[item.status] += 1
            by_risk_level[item.decision.risk_level] += 1

            if item.status in (PENDING, EXPIRED):
                stuck_items.append(
                    {
                        "item_id": item.item_id,
                        "scope_id": item.scope_id,
                        "status": item.status,
                        "risk_level": item.decision.risk_level,
                        "created_at": item.created_at,
                        "expires_at": item.expires_at,
                    }
                )

            if item.status == CLAIMED and item.claimed_by:
                reviewer_workload.setdefault(item.claimed_by, {"active": 0, "resolved": 0})
                reviewer_workload[item.claimed_by]["active"] += 1

            if item.status == RESOLVED:
                outcome = (item.resolution or {}).get("outcome")
                if outcome in by_outcome:
                    by_outcome[outcome] += 1

                if item.resolved_by:
                    reviewer_workload.setdefault(item.resolved_by, {"active": 0, "resolved": 0})
                    reviewer_workload[item.resolved_by]["resolved"] += 1

                if item.resolved_at is not None:
                    resolution_seconds_total += (item.resolved_at - item.created_at).total_seconds()
                    resolved_count += 1

        average_resolution_seconds = (
            resolution_seconds_total / resolved_count if resolved_count else 0.0
        )

        return ReviewMetrics(
            scope_id=scope_id,
            total=len(items),
            by_status=by_status,
            by_outcome=by_outcome,
            by_risk_level=by_risk_level,
            average_resolution_seconds=average_resolution_seconds,
            reviewer_workload=reviewer_workload,
            stuck_items=stuck_items,
        )
