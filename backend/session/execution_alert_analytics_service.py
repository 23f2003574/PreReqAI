from datetime import (
    datetime,
    timezone,
)

from .execution_alert_analytics import (
    ExecutionAlertAnalytics,
)

from .execution_alert_analytics_error import (
    ExecutionAlertAnalyticsError,
)

_CRITICAL_SEVERITY = "ERROR"

_STATUS_OPEN = "OPEN"

_STATUS_RESOLVED = "RESOLVED"


class ExecutionAlertAnalyticsService:
    """
    Turns a runtime's raw alert history into actionable trends,
    performing read-only aggregation only.

    Composes with existing observability services (duck-typed to what
    each already exposes):
        alert_service: history(runtime_id) -> tuple of objects with
            .severity, .status, .triggered_at (ExecutionAlertService)
        deduplication_service: fingerprint(alert) -> str
            (ExecutionAlertDeduplicationService)

    The service performs no alert triggering, resolution, or
    fingerprint recording of its own, and never mutates either
    composed service; every method here only reads what has already
    been recorded elsewhere. Correlation membership is deliberately
    not consulted: a runtime's totals reflect every alert actually
    triggered on it, whether or not that alert was later grouped into
    a cross-runtime correlation elsewhere, so correlated alerts are
    still counted correctly rather than being hidden or double
    counted.

    Behavior:
    - severity_breakdown() counts a runtime's recorded alerts by
      severity, only for severities that actually occurred
    - recurrence() groups a runtime's recorded alerts by
      deduplication_service.fingerprint() (a pure function, so this
      never mutates the deduplication service) and reports how many
      of them are repeat occurrences of an already-seen condition
    - trend() reports a runtime's recorded alerts, oldest to newest,
      as lightweight (triggered_at, severity, status) entries
    - generate() combines totals, open/resolved counts,
      severity_breakdown(), and recurrence() into a single record
    - A runtime with no recorded alerts produces empty aggregates
      rather than raising
    - Every method is a pure function of the currently recorded data:
      calling it again without any new alert recorded in between
      always produces the same result

    The service is:
    - Thread-safe: it holds no state of its own; every method reads
      directly from the composed services
    """

    def __init__(self, alert_service, deduplication_service):
        self._alert_service = alert_service
        self._deduplication_service = deduplication_service

    def generate(self, runtime_id: str) -> ExecutionAlertAnalytics:
        """
        Compute a fresh analytics record for runtime_id.

        Raises:
            ExecutionAlertAnalyticsError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        history = self._alert_service.history(runtime_id)

        breakdown = self._severity_breakdown(history)
        recurrence_stats = self._recurrence(history)

        return ExecutionAlertAnalytics(
            runtime_id=runtime_id,
            total_alerts=len(history),
            open_alerts=sum(1 for alert in history if alert.status == _STATUS_OPEN),
            resolved_alerts=sum(1 for alert in history if alert.status == _STATUS_RESOLVED),
            critical_count=breakdown.get(_CRITICAL_SEVERITY, 0),
            recurrence_rate=recurrence_stats["recurrence_rate"],
            generated_at=datetime.now(timezone.utc),
        )

    def trend(self, runtime_id: str) -> tuple:
        """
        runtime_id's recorded alerts, oldest to newest, as
        {"triggered_at", "severity", "status"} entries.

        Raises:
            ExecutionAlertAnalyticsError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        history = self._alert_service.history(runtime_id)

        return tuple(
            {
                "triggered_at": alert.triggered_at,
                "severity": alert.severity,
                "status": alert.status,
            }
            for alert in history
        )

    def severity_breakdown(self, runtime_id: str) -> dict:
        """
        runtime_id's recorded alert counts, grouped by severity.

        Raises:
            ExecutionAlertAnalyticsError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        return self._severity_breakdown(self._alert_service.history(runtime_id))

    def recurrence(self, runtime_id: str) -> dict:
        """
        runtime_id's recurrence statistics: total_alerts,
        distinct_conditions (unique fingerprints), and
        recurrence_rate (the fraction of total_alerts beyond each
        condition's first occurrence).

        Raises:
            ExecutionAlertAnalyticsError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        return self._recurrence(self._alert_service.history(runtime_id))

    def _severity_breakdown(self, history) -> dict:
        breakdown = {}

        for alert in history:
            breakdown[alert.severity] = breakdown.get(alert.severity, 0) + 1

        return breakdown

    def _recurrence(self, history) -> dict:
        total_alerts = len(history)

        if total_alerts == 0:
            return {"total_alerts": 0, "distinct_conditions": 0, "recurrence_rate": 0.0}

        fingerprints = {self._deduplication_service.fingerprint(alert) for alert in history}
        distinct_conditions = len(fingerprints)

        return {
            "total_alerts": total_alerts,
            "distinct_conditions": distinct_conditions,
            "recurrence_rate": (total_alerts - distinct_conditions) / total_alerts,
        }

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionAlertAnalyticsError(f"Cannot use an empty or blank {field_name}.")
