from ..secret_redaction import LLMSecretRedactionService
from ..security_audit import INPUT, OUTPUT, LLMSecurityAuditService
from ..security_policy import ALLOW, BLOCK, REDACT


class SecretInScopeError(ValueError):
    """Raised when a scope string looks like it carries a credential."""


class LLMSecurityMetricsService:
    """Read-only aggregate metrics over Commit #6's own security audit
    trail -- no new telemetry system, no new audit model.

    Reuses LLMSecurityAuditService.records(scope) as the sole source of
    truth (added alongside this commit, mirroring
    backend.llm.usage.LLMUsageService.records(scope_id) exactly: scope is
    a request_id, None means every recorded request, and an unrecognized
    scope yields an empty result rather than an error -- a scope with
    nothing recorded is a valid, empty answer, not a failure). period is
    the same (start, end) datetime pair backend.llm.observability_dashboard
    already uses; a record counts only when its created_at falls within
    it.

    Every audit record was already emptied of payload/secret content by
    Commit #6's own rules -- decision, policy_ids, and finding_types are
    labels only -- so nothing aggregated here can expose a sensitive
    value either; the one string a caller controls directly, scope, is
    checked against Commit #3's own secret detection before any query
    runs, the same guard backend.llm.observability_dashboard already
    applies to its own scope parameter (there via a local pattern copy;
    here via the canonical LLMSecretRedactionService those patterns were
    consolidated into).

    Nothing here writes anything: aggregating never touches
    LLMSecurityAuditService's own state, and no policy decision is ever
    made, changed, or re-evaluated by this commit (see Constraints: "No
    policy changes in this commit").
    """

    def __init__(
        self,
        audit_service: LLMSecurityAuditService,
        secret_redaction_service: LLMSecretRedactionService = None,
    ):
        self._audit_service = audit_service
        self._secret_redaction = secret_redaction_service or LLMSecretRedactionService()

    @staticmethod
    def _require_valid_period(period):
        start, end = period
        if start > end:
            raise ValueError("period start must not be after end")
        return start, end

    def _require_safe_scope(self, scope) -> None:
        if scope is not None and self._secret_redaction.contains_secret(scope):
            raise SecretInScopeError(f"scope {scope!r} looks like it carries a credential")

    def _records(self, scope, period) -> tuple:
        self._require_safe_scope(scope)
        start, end = self._require_valid_period(period)
        return tuple(
            audit for audit in self._audit_service.records(scope) if start <= audit.created_at <= end
        )

    @staticmethod
    def _empty_bucket() -> dict:
        return {"allowed": 0, "redacted": 0, "blocked": 0, "findings": {}}

    @staticmethod
    def _accumulate(bucket: dict, audit) -> None:
        if audit.decision == ALLOW:
            bucket["allowed"] += 1
        elif audit.decision == REDACT:
            bucket["redacted"] += 1
        elif audit.decision == BLOCK:
            bucket["blocked"] += 1
        for finding_type in audit.finding_types:
            bucket["findings"][finding_type] = bucket["findings"].get(finding_type, 0) + 1

    def summary(self, scope, period) -> dict:
        """allowed/redacted/blocked counts and a finding_type histogram for
        every audit record matching `scope`, recorded within `period`.

        Always returns all four keys -- zero-valued and an empty
        findings dict when nothing matches, never omitted or None (see
        Rules: "Missing data remains explicit").
        """
        bucket = self._empty_bucket()
        for audit in self._records(scope, period):
            self._accumulate(bucket, audit)
        return bucket

    def by_policy(self, scope, period) -> dict:
        """summary()'s own breakdown, grouped by every Commit #4 policy_id
        that applied.

        A record naming no policy (Commit #6's own policy_ids is empty
        whenever none applied) contributes to no group here -- there is
        nothing to attribute it to.
        """
        groups = {}
        for audit in self._records(scope, period):
            for policy_id in audit.policy_ids:
                groups.setdefault(policy_id, self._empty_bucket())
                self._accumulate(groups[policy_id], audit)
        return groups

    def by_decision(self, scope, period) -> dict:
        """Record count and finding_type histogram, grouped by decision.

        Always reports all three of ALLOW/REDACT/BLOCK, zero-valued when
        a decision has no matching record.
        """
        groups = {decision: {"count": 0, "findings": {}} for decision in (ALLOW, REDACT, BLOCK)}
        for audit in self._records(scope, period):
            group = groups[audit.decision]
            group["count"] += 1
            for finding_type in audit.finding_types:
                group["findings"][finding_type] = group["findings"].get(finding_type, 0) + 1
        return groups

    def by_direction(self, scope, period) -> dict:
        """summary()'s own breakdown, grouped by INPUT vs OUTPUT (see Rules:
        "Distinguish input vs output").

        Always reports both directions, zero-valued when one has no
        matching record.
        """
        groups = {direction: self._empty_bucket() for direction in (INPUT, OUTPUT)}
        for audit in self._records(scope, period):
            self._accumulate(groups[audit.direction], audit)
        return groups
