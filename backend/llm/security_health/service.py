from datetime import datetime, timezone

from ..output_security import SECRETS
from ..security_metrics import LLMSecurityMetricsService

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
CRITICAL = "CRITICAL"
UNKNOWN = "UNKNOWN"
STATUSES = frozenset({HEALTHY, DEGRADED, CRITICAL, UNKNOWN})


class LLMSecurityHealthService:
    """One HEALTHY/DEGRADED/CRITICAL/UNKNOWN verdict from Commit #9's own
    security metrics -- the security-policy counterpart of
    LLMObservabilityHealthService, built the same way that service is:
    every input is an existing Commit #9 aggregate (summary(scope,
    period)), and this service adds no detection, aggregation, or
    monitoring of its own beyond the handful of status thresholds it owns
    explicitly, since no security-health threshold already exists
    anywhere in this project. Nothing here ever mutates a policy, an
    audit record, or anything upstream of it (see Constraints: "No
    automatic remediation").

    Status is decided from summary() alone, in the fixed order the Rules
    specify: no recorded decision at all is UNKNOWN (there is nothing to
    judge); any BLOCK is CRITICAL (Commit #5 only ever blocks an
    unaddressable finding or an explicit sensitive-data BLOCK -- never
    something trivial); any REDACT, or any finding raised on a record
    that was not blocked (e.g. a SECRETS finding an operator explicitly
    allowed through -- see Commit #5's own combine()), is a "significant
    non-blocking finding" and DEGRADED; anything else -- decisions
    recorded, nothing flagged -- is HEALTHY. Because status only reads
    summary()'s own counts, the same audit state always produces the
    same status (see Rules: "Deterministic result").
    """

    def __init__(self, metrics_service: LLMSecurityMetricsService):
        self._metrics_service = metrics_service

    @staticmethod
    def _finding_severity(finding_type: str) -> str:
        # Every Commit #1/#2 category except SECRETS is unconditionally
        # hard-blocking (see LLMSecurityPolicyService._combine()), so its
        # mere presence already implies a BLOCK the "blocking_events"
        # check below also reports. SECRETS is the one category that can
        # appear on an ALLOW or REDACT record too, so its own occurrence
        # is reported as DEGRADED rather than assumed CRITICAL.
        return DEGRADED if finding_type == SECRETS else CRITICAL

    def assess(self, scope, period) -> dict:
        """The full assessment for scope over period: status, findings, timestamp."""
        summary = self._metrics_service.summary(scope, period)
        total = summary["allowed"] + summary["redacted"] + summary["blocked"]

        findings = []

        if total == 0:
            findings.append(
                {
                    "check": "data_sufficiency",
                    "severity": UNKNOWN,
                    "detail": "no security-audit records for this scope/period",
                }
            )
            return {
                "status": UNKNOWN,
                "findings": findings,
                "assessed_at": datetime.now(timezone.utc),
            }

        findings.append(
            {
                "check": "data_sufficiency",
                "severity": HEALTHY,
                "detail": f"{total} security decision(s) recorded",
            }
        )

        if summary["blocked"] > 0:
            findings.append(
                {
                    "check": "blocking_events",
                    "severity": CRITICAL,
                    "detail": f"{summary['blocked']} request(s) blocked",
                }
            )

        if summary["redacted"] > 0:
            findings.append(
                {
                    "check": "redaction_events",
                    "severity": DEGRADED,
                    "detail": f"{summary['redacted']} request(s) redacted",
                }
            )

        for finding_type in sorted(summary["findings"]):
            count = summary["findings"][finding_type]
            findings.append(
                {
                    "check": f"finding:{finding_type}",
                    "severity": self._finding_severity(finding_type),
                    "detail": f"{count} occurrence(s) of {finding_type}",
                }
            )

        return {
            "status": self._overall(findings),
            "findings": findings,
            "assessed_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def _overall(findings: list) -> str:
        severities = {finding["severity"] for finding in findings}
        if CRITICAL in severities:
            return CRITICAL
        if DEGRADED in severities:
            return DEGRADED
        return HEALTHY

    def status(self, scope, period) -> str:
        return self.assess(scope, period)["status"]

    def findings(self, scope, period) -> list:
        return self.assess(scope, period)["findings"]
