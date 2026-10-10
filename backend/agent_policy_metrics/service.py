import re
from datetime import datetime

from backend.agent_policy_audit import LLMAgentPolicyAuditService
from backend.agent_policy_engine import ALLOW, DENY

from .models import PolicyMetrics

# Same secret-detection convention already kept locally by
# backend.agent_policy_audit, backend.agent_strategy_decision_audit,
# backend.llm.tool_audit, and every other module in this repository that
# needs it -- kept local here too rather than refactoring any of those.
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


class SecretInScopeError(ValueError):
    """Raised when a scope_id looks like it carries a credential."""


class InvalidMetricsFilterError(ValueError):
    """Raised when filters is malformed."""


class LLMAgentPolicyMetricsService:
    """Read-only aggregate metrics over Commit #7's own policy decision
    audit trail -- no new telemetry system, no new audit model.

    Mirrors backend.llm.security_metrics.LLMSecurityMetricsService
    exactly: the audit service's own list_for_scope() is the sole source
    of truth (never a second store, never duplicated state -- see Rules:
    "Do not store duplicate metric state"), an unrecognized or empty
    scope yields a clean, zero-valued PolicyMetrics rather than an error,
    and every count is a pure read -- summarize() never writes anything,
    never calls LLMAgentPolicyEnforcement/LLMAgentPolicyEvaluator, and
    never changes a single past decision.

    Every Commit #7 audit record was already emptied of the action's own
    arguments/payload (see LLMAgentPolicyDecisionAudit: "what is
    deliberately absent"), so nothing aggregated here can expose one
    either; the one string a caller controls directly, scope_id, is
    checked against the same secret-detection convention this whole
    series already keeps locally -- the same guard
    LLMSecurityMetricsService already applies to its own scope parameter.
    """

    def __init__(self, audit_service: LLMAgentPolicyAuditService):
        self._audit_service = audit_service

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

        decision = filters.get("decision")
        if decision is not None and decision not in (ALLOW, DENY):
            raise InvalidMetricsFilterError(f"filters['decision'] must be one of ({ALLOW!r}, {DENY!r})")

        return filters

    def _matching_records(self, scope_id: str, filters) -> list:
        self._require_safe_scope(scope_id)
        filters = self._validate_filters(filters)

        start = filters.get("start")
        end = filters.get("end")
        decision = filters.get("decision")
        policy_id = filters.get("policy_id")
        rule_id = filters.get("rule_id")

        matching = []
        for record in self._audit_service.list_for_scope(scope_id):
            if start is not None and record.created_at < start:
                continue
            if end is not None and record.created_at > end:
                continue
            if decision is not None and record.decision != decision:
                continue
            if policy_id is not None and not any(
                rule["policy_id"] == policy_id for rule in record.matched_rules
            ):
                continue
            if rule_id is not None and not any(rule["rule_id"] == rule_id for rule in record.matched_rules):
                continue
            matching.append(record)
        return matching

    @staticmethod
    def _empty_bucket() -> dict:
        return {"total": 0, "allowed": 0, "denied": 0}

    @staticmethod
    def _accumulate(bucket: dict, record) -> None:
        bucket["total"] += 1
        if record.decision == ALLOW:
            bucket["allowed"] += 1
        elif record.decision == DENY:
            bucket["denied"] += 1

    def summarize(self, scope_id: str, filters: dict = None) -> PolicyMetrics:
        """Aggregate every Commit #7 audit record for scope_id (narrowed
        by `filters`, when given) into one PolicyMetrics snapshot.

        filters, all optional and combined with AND: start/end (datetime
        bounds on created_at, inclusive), decision (ALLOW or DENY),
        policy_id/rule_id (only records whose matched_rules name it).

        Raises:
            ValueError: If scope_id is missing
            SecretInScopeError: If scope_id looks like it carries a credential
            InvalidMetricsFilterError: If filters is malformed
        """
        records = self._matching_records(scope_id, filters)

        overall = self._empty_bucket()
        by_policy: dict = {}
        by_rule: dict = {}
        by_period: dict = {}
        exception_assisted = 0

        for record in records:
            self._accumulate(overall, record)
            if record.exceptions:
                exception_assisted += 1

            for entry_policy_id in {rule["policy_id"] for rule in record.matched_rules}:
                self._accumulate(by_policy.setdefault(entry_policy_id, self._empty_bucket()), record)

            for entry_rule_id in {rule["rule_id"] for rule in record.matched_rules}:
                self._accumulate(by_rule.setdefault(entry_rule_id, self._empty_bucket()), record)

            day = record.created_at.date().isoformat()
            self._accumulate(by_period.setdefault(day, self._empty_bucket()), record)

        total = overall["total"]
        denial_rate = (overall["denied"] / total) if total else 0.0

        return PolicyMetrics(
            scope_id=scope_id,
            total=total,
            allowed=overall["allowed"],
            denied=overall["denied"],
            exception_assisted=exception_assisted,
            denial_rate=denial_rate,
            by_policy=by_policy,
            by_rule=by_rule,
            by_period=by_period,
        )
