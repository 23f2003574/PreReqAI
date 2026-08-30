import dataclasses
from datetime import datetime, timezone

from ..usage_anomalies import NORMAL, UNKNOWN, LLMUsageAnomalyService
from .models import OPEN, RESOLVED, LLMUsageAnomalyAlert


class NotAnomalousError(ValueError):
    """Raised when create() is called for an anomaly that was not confirmed
    (severity NORMAL or UNKNOWN)."""


class DuplicateAlertError(ValueError):
    """Raised when an unresolved alert already exists for the same anomaly_id."""


class UnknownAlertError(KeyError):
    """Raised when looking up an alert_id that was never created."""


class LLMUsageAnomalyAlertService:
    """Turns a Commit #7 confirmed anomaly into a structured, actionable alert.

    Reuses Commit #7's LLMUsageAnomaly end to end -- no second detection or
    notification system, and no automatic remediation: create()/resolve()
    are the only ways an alert's lifecycle ever changes, both requiring an
    explicit caller.
    """

    def __init__(self, anomaly_service: LLMUsageAnomalyService):
        self._anomaly_service = anomaly_service
        self._alerts = {}
        self._by_scope = {}
        self._unresolved_by_anomaly = {}
        self._counter = 0

    @staticmethod
    def _message(anomaly) -> str:
        return (
            f"{anomaly.metric} anomaly detected for scope {anomaly.scope!r}: "
            f"observed={anomaly.observed}, baseline={anomaly.baseline}, "
            f"deviation={anomaly.deviation} (severity={anomaly.severity})"
        )

    def create(self, anomaly_id: str) -> LLMUsageAnomalyAlert:
        anomaly = self._anomaly_service.get(anomaly_id)

        if anomaly.severity in (NORMAL, UNKNOWN):
            raise NotAnomalousError(
                f"anomaly {anomaly_id!r} has severity {anomaly.severity!r}; only a "
                "confirmed anomaly can be alerted on"
            )

        if anomaly_id in self._unresolved_by_anomaly:
            raise DuplicateAlertError(
                f"an unresolved alert already exists for anomaly {anomaly_id!r}"
            )

        self._counter += 1
        alert = LLMUsageAnomalyAlert(
            alert_id=f"alert-{self._counter}",
            anomaly_id=anomaly_id,
            severity=anomaly.severity,
            status=OPEN,
            message=self._message(anomaly),
            created_at=datetime.now(timezone.utc),
            resolved_at=None,
        )
        alert.validate()

        self._alerts[alert.alert_id] = alert
        self._by_scope.setdefault(anomaly.scope, []).append(alert.alert_id)
        self._unresolved_by_anomaly[anomaly_id] = alert.alert_id
        return alert

    def _get(self, alert_id: str) -> LLMUsageAnomalyAlert:
        try:
            return self._alerts[alert_id]
        except KeyError:
            raise UnknownAlertError(alert_id)

    def resolve(self, alert_id: str) -> LLMUsageAnomalyAlert:
        """Explicitly resolve alert_id. Resolving an already-resolved alert is a no-op."""
        alert = self._get(alert_id)
        if alert.status == RESOLVED:
            return alert

        resolved = dataclasses.replace(
            alert, status=RESOLVED, resolved_at=datetime.now(timezone.utc)
        )
        resolved.validate()

        self._alerts[alert_id] = resolved
        self._unresolved_by_anomaly.pop(alert.anomaly_id, None)
        return resolved

    def list(self, scope) -> list:
        """Every alert ever created for scope, resolved or not, in creation order."""
        return [self._alerts[alert_id] for alert_id in self._by_scope.get(scope, [])]

    def unresolved(self, scope) -> list:
        """The still-open alerts for scope."""
        return [alert for alert in self.list(scope) if alert.status == OPEN]
