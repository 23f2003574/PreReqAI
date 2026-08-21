from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_observability_alert import (
    ExecutionObservabilityAlert,
    STATUS_OPEN,
    STATUS_RESOLVED,
)

from .execution_observability_alert_error import (
    ExecutionObservabilityAlertError,
)


class ExecutionAlertService:
    """
    Persists triggered alerts as their own instances, separate from
    the reusable alert rules they were triggered from.

    Composes with existing observability services (duck-typed to what
    each already exposes):
        alert_rule_service: evaluate(runtime_id) -> tuple of objects
            with .rule_id, .metric, .severity
            (ExecutionAlertRuleService)
        metrics_service: latest(runtime_id, name) -> object with
            .value (ExecutionMetricsService)

    Performs no rule evaluation or metric recording of its own, and
    never mutates either composed service; every alert is produced
    from what they currently report.

    Behavior:
    - trigger() creates a new OPEN alert, but only for a rule_id that
      is currently among runtime_id's triggered rules (per
      alert_rule_service.evaluate()); the alert's value is the metric
      value observed at that moment, preserved unchanged for the
      alert's lifetime
    - resolve() is idempotent: resolving an already-RESOLVED alert
      simply returns it unchanged
    - active() reports a runtime's currently-OPEN alerts
    - history() reports every alert ever triggered for a runtime,
      oldest to newest
    - get() reports a single alert by alert_id

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, alert_rule_service, metrics_service):
        self._alert_rule_service = alert_rule_service
        self._metrics_service = metrics_service
        self._alerts_by_id = {}
        self._lock = RLock()

    def trigger(self, runtime_id: str, rule_id: str) -> ExecutionObservabilityAlert:
        """
        Create a new OPEN alert for rule_id against runtime_id.

        Raises:
            ExecutionObservabilityAlertError: If runtime_id or
                rule_id is None or blank, or rule_id is not currently
                among runtime_id's triggered rules
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(rule_id, "rule ID")

        rule = self._resolve_triggered_rule(runtime_id, rule_id)

        metric = self._metrics_service.latest(runtime_id, rule.metric)

        if metric is None:
            raise ExecutionObservabilityAlertError(
                f"Cannot trigger an alert for rule ID {rule_id!r}: "
                f"no metric value is recorded for runtime ID {runtime_id!r}."
            )

        with self._lock:
            alert = ExecutionObservabilityAlert(
                alert_id=str(uuid4()),
                rule_id=rule_id,
                runtime_id=runtime_id,
                severity=rule.severity,
                value=metric.value,
                status=STATUS_OPEN,
                triggered_at=datetime.now(timezone.utc),
                resolved_at=None,
            )

            self._alerts_by_id[alert.alert_id] = alert

            return alert

    def active(self, runtime_id: str) -> tuple:
        """
        runtime_id's currently-OPEN alerts, oldest to newest.

        Raises:
            ExecutionObservabilityAlertError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            matching = [
                alert
                for alert in self._alerts_by_id.values()
                if alert.runtime_id == runtime_id and alert.status == STATUS_OPEN
            ]

        return tuple(sorted(matching, key=lambda alert: alert.triggered_at))

    def resolve(self, alert_id: str) -> ExecutionObservabilityAlert:
        """
        Resolve an alert. Idempotent: resolving an already-RESOLVED
        alert simply returns it unchanged.

        Raises:
            ExecutionObservabilityAlertError: If alert_id is None or
                blank, or no alert is registered under it
        """

        self._validate_text(alert_id, "alert ID")

        with self._lock:
            alert = self._resolve(alert_id)

            if alert.status == STATUS_RESOLVED:
                return alert

            resolved = replace(
                alert,
                status=STATUS_RESOLVED,
                resolved_at=datetime.now(timezone.utc),
            )
            self._alerts_by_id[alert_id] = resolved

            return resolved

    def history(self, runtime_id: str) -> tuple:
        """
        Every alert ever triggered for runtime_id, oldest to newest.

        Raises:
            ExecutionObservabilityAlertError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            matching = [
                alert
                for alert in self._alerts_by_id.values()
                if alert.runtime_id == runtime_id
            ]

        return tuple(sorted(matching, key=lambda alert: alert.triggered_at))

    def get(self, alert_id: str) -> ExecutionObservabilityAlert:
        """
        The alert registered under alert_id.

        Raises:
            ExecutionObservabilityAlertError: If alert_id is None or
                blank, or no alert is registered under it
        """

        self._validate_text(alert_id, "alert ID")

        with self._lock:
            return self._resolve(alert_id)

    def _resolve_triggered_rule(self, runtime_id: str, rule_id: str):
        triggered_rules = self._alert_rule_service.evaluate(runtime_id)
        rule = next((rule for rule in triggered_rules if rule.rule_id == rule_id), None)

        if rule is None:
            raise ExecutionObservabilityAlertError(
                f"Cannot trigger an alert for rule ID {rule_id!r}: "
                f"it is not currently triggered for runtime ID {runtime_id!r}."
            )

        return rule

    def _resolve(self, alert_id: str) -> ExecutionObservabilityAlert:
        alert = self._alerts_by_id.get(alert_id)

        if alert is None:
            raise ExecutionObservabilityAlertError(
                f"No alert is recorded under alert ID {alert_id!r}."
            )

        return alert

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertError(f"Cannot use an empty or blank {field_name}.")
