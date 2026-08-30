from datetime import datetime, timezone

from ..budget import UnknownBudgetError
from ..budget_analytics import LLMBudgetAnalyticsService
from ..observability_dashboard import LLMObservabilityDashboardService
from ..usage_anomalies import CRITICAL as ANOMALY_CRITICAL
from ..usage_anomalies import MODERATE as ANOMALY_MODERATE

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
CRITICAL = "CRITICAL"
UNKNOWN = "UNKNOWN"
STATUSES = frozenset({HEALTHY, DEGRADED, CRITICAL, UNKNOWN})

DEFAULT_DEGRADED_FAILURE_RATE = 0.1
DEFAULT_CRITICAL_FAILURE_RATE = 0.3


class LLMObservabilityHealthService:
    """One HEALTHY/DEGRADED/CRITICAL/UNKNOWN verdict from Commit #9's dashboard data.

    Reuses LLMObservabilityDashboardService.summary() end to end -- usage,
    cost, latency, error_rate, provider_reliability, and Commit #7's own
    anomalies -- so every threshold that already exists (an anomaly's
    configured moderate/critical deviation bounds, and Commit #6's budget
    limits when a budget_analytics is supplied) is the one actually
    considered; this service adds no scoring or detection of its own
    beyond a couple of failure_rate bounds it owns explicitly, since no
    error-rate health threshold already exists anywhere in this project.
    Nothing here ever mutates data or switches a provider.
    """

    def __init__(
        self,
        dashboard_service: LLMObservabilityDashboardService,
        budget_analytics: LLMBudgetAnalyticsService = None,
        degraded_failure_rate: float = DEFAULT_DEGRADED_FAILURE_RATE,
        critical_failure_rate: float = DEFAULT_CRITICAL_FAILURE_RATE,
    ):
        self._dashboard_service = dashboard_service
        self._budget_analytics = budget_analytics
        self._degraded_failure_rate = degraded_failure_rate
        self._critical_failure_rate = critical_failure_rate

    def _check_error_rate(self, findings: list, failure_rate: float):
        if failure_rate > self._critical_failure_rate:
            findings.append(
                {
                    "check": "error_rate",
                    "severity": CRITICAL,
                    "detail": f"failure_rate {failure_rate} exceeds critical threshold "
                    f"{self._critical_failure_rate}",
                }
            )
        elif failure_rate > self._degraded_failure_rate:
            findings.append(
                {
                    "check": "error_rate",
                    "severity": DEGRADED,
                    "detail": f"failure_rate {failure_rate} exceeds degraded threshold "
                    f"{self._degraded_failure_rate}",
                }
            )
        else:
            findings.append(
                {
                    "check": "error_rate",
                    "severity": HEALTHY,
                    "detail": f"failure_rate {failure_rate} is within acceptable range",
                }
            )

    @staticmethod
    def _check_anomalies(findings: list, anomalies: list):
        for anomaly in anomalies:
            if anomaly.severity == ANOMALY_CRITICAL:
                severity = CRITICAL
            elif anomaly.severity == ANOMALY_MODERATE:
                severity = DEGRADED
            else:
                continue

            findings.append(
                {
                    "check": f"anomaly:{anomaly.metric}",
                    "severity": severity,
                    "detail": (
                        f"{anomaly.metric} observed={anomaly.observed} "
                        f"baseline={anomaly.baseline} deviation={anomaly.deviation}"
                    ),
                }
            )

    def _check_budget(self, findings: list, scope):
        if self._budget_analytics is None:
            return
        try:
            utilization = self._budget_analytics.utilization(scope)
        except UnknownBudgetError:
            return

        if utilization["over_budget"]:
            findings.append(
                {
                    "check": "budget",
                    "severity": CRITICAL,
                    "detail": (
                        f"scope is over its configured budget "
                        f"(tokens={utilization['tokens']}, cost={utilization['cost']})"
                    ),
                }
            )
        else:
            findings.append(
                {
                    "check": "budget",
                    "severity": HEALTHY,
                    "detail": "scope is within its configured budget",
                }
            )

    @staticmethod
    def _overall(findings: list) -> str:
        severities = {finding["severity"] for finding in findings}
        if CRITICAL in severities:
            return CRITICAL
        if DEGRADED in severities:
            return DEGRADED
        return HEALTHY

    def assess(self, scope, period, summary: dict = None) -> dict:
        """The full assessment for scope over period: status, findings, timestamp.

        Pass summary (Commit #9's own summary(scope, period) result) when a
        caller already fetched it, so it is never computed twice; omit it
        to have this method fetch it itself.
        """
        if summary is None:
            summary = self._dashboard_service.summary(scope, period)
        reliability = summary["provider_reliability"]

        findings = []

        if reliability["count"] == 0:
            findings.append(
                {
                    "check": "data_sufficiency",
                    "severity": UNKNOWN,
                    "detail": "no completed requests recorded in this period",
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
                "detail": f"{reliability['count']} completed request(s) recorded",
            }
        )

        self._check_error_rate(findings, reliability["failure_rate"])
        self._check_anomalies(findings, summary["anomalies"])
        self._check_budget(findings, scope)

        return {
            "status": self._overall(findings),
            "findings": findings,
            "assessed_at": datetime.now(timezone.utc),
        }

    def status(self, scope, period) -> str:
        return self.assess(scope, period)["status"]

    def findings(self, scope, period) -> list:
        return self.assess(scope, period)["findings"]
