import dataclasses

from ..observability_dashboard import LLMObservabilityDashboardService
from ..observability_health import LLMObservabilityHealthService
from ..observability_reports import LLMObservabilityReportService
from ..usage_anomalies import CRITICAL as ANOMALY_CRITICAL
from ..usage_anomalies import MODERATE as ANOMALY_MODERATE
from ..usage_anomaly_alerts import DuplicateAlertError, LLMUsageAnomalyAlertService


class LLMObservabilityOrchestrationService:
    """The single entrypoint tying Commits #1-#12's observability layer together.

    Every field this service returns is produced by an existing service --
    Commit #9's dashboard summary for metrics/cost/reliability/anomalies,
    Commit #8's alert service for propagating confirmed anomalies into
    alerts, Commit #12's health assessment, and Commit #10's report export
    -- so there is no new telemetry, scoring, or comparison logic here.
    Commit #9's summary(scope, period) is fetched exactly once per call and
    threaded into health()/report() so their own dashboard reads are never
    duplicated. The only state this service ever changes is creating
    Commit #8 alert records for anomalies confirmed in the period being
    read -- that is alert propagation, the explicit purpose of composing
    Commit #8 here, not remediation: nothing routes a request, retries
    anything, or touches a provider/model configuration.
    """

    def __init__(
        self,
        dashboard_service: LLMObservabilityDashboardService,
        health_service: LLMObservabilityHealthService,
        alert_service: LLMUsageAnomalyAlertService,
        report_service: LLMObservabilityReportService,
    ):
        self._dashboard_service = dashboard_service
        self._health_service = health_service
        self._alert_service = alert_service
        self._report_service = report_service

    def _sync_alerts(self, scope, anomalies) -> list:
        """Ensure a Commit #8 alert exists for every confirmed anomaly in anomalies,
        then return scope's currently unresolved alerts."""
        for anomaly in anomalies:
            if anomaly.severity in (ANOMALY_MODERATE, ANOMALY_CRITICAL):
                try:
                    self._alert_service.create(anomaly.anomaly_id)
                except DuplicateAlertError:
                    continue
        return self._alert_service.unresolved(scope)

    def analyze(self, scope, period) -> dict:
        """One structured result: metrics, cost, reliability, anomalies, alerts, health."""
        summary = self._dashboard_service.summary(scope, period)
        alerts = self._sync_alerts(scope, summary["anomalies"])
        health = self._health_service.assess(scope, period, summary=summary)

        return {
            "metrics": {
                "usage": summary["usage"],
                "latency": summary["latency"],
                "error_rate": summary["error_rate"],
            },
            "cost": summary["cost"],
            "reliability": summary["provider_reliability"],
            "anomalies": summary["anomalies"],
            "alerts": alerts,
            "health": health,
        }

    @staticmethod
    def _alert_to_dict(alert) -> dict:
        payload = dataclasses.asdict(alert)
        payload["created_at"] = alert.created_at.isoformat()
        payload["resolved_at"] = alert.resolved_at.isoformat() if alert.resolved_at else None
        return payload

    def report(self, scope, period) -> dict:
        """Commit #10's exportable report, enriched with alerts and health."""
        summary = self._dashboard_service.summary(scope, period)
        alerts = self._sync_alerts(scope, summary["anomalies"])
        health = self._health_service.assess(scope, period, summary=summary)

        report = self._report_service.generate(scope, period, summary=summary)
        report["alerts"] = [self._alert_to_dict(alert) for alert in alerts]
        report["health"] = {
            "status": health["status"],
            "findings": health["findings"],
            "assessed_at": health["assessed_at"].isoformat(),
        }
        return report

    def health(self, scope, period) -> dict:
        """Commit #12's health assessment for scope over period, unchanged."""
        return self._health_service.assess(scope, period)

    def alerts(self, scope, period) -> list:
        """Confirmed anomalies for scope over period, propagated into Commit #8 alerts."""
        summary = self._dashboard_service.summary(scope, period)
        return self._sync_alerts(scope, summary["anomalies"])
