from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_observation_alert_error import (
    ExecutionObservationAlertError,
)

from .execution_observation_alert import (
    ExecutionObservationAlert,
)

_COMPARISONS = {
    ">": lambda value, threshold: value > threshold,
    "<": lambda value, threshold: value < threshold,
    ">=": lambda value, threshold: value >= threshold,
    "<=": lambda value, threshold: value <= threshold,
}


class ExecutionObservationAlertService:
    """
    Evaluates a session's registered alerts against observed metric
    values, triggering the ones whose threshold is crossed.

    The service's responsibility is alert bookkeeping and evaluation
    only. It does not observe metrics or errors itself; observation
    metrics and errors are assumed to already exist, and a caller
    passes the value to check against a session's alerts to
    evaluate().

    Behavior:
    - evaluate() only considers ENABLED alerts watching the given
      metric_type; a disabled alert never triggers
    - A triggered alert stays triggered across repeated evaluate()
      calls until resolve() clears it
    - resolve() clears a triggered alert's state, after which it may
      trigger again on a future evaluate()
    - active() lists only a session's currently triggered alerts

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._alerts_by_id = {}
        self._alert_ids_by_session = {}
        self._lock = RLock()

    def register(self, alert: ExecutionObservationAlert) -> ExecutionObservationAlert:
        """
        Register a new alert.

        Raises:
            ExecutionObservationAlertError: If alert is not an
                ExecutionObservationAlert, or its alert ID is already
                registered
        """

        if not isinstance(alert, ExecutionObservationAlert):
            raise ExecutionObservationAlertError(
                "Cannot register an invalid alert: alert must be an ExecutionObservationAlert."
            )

        with self._lock:
            if alert.alert_id in self._alerts_by_id:
                raise ExecutionObservationAlertError(f"Alert ID {alert.alert_id!r} is already registered.")

            self._alerts_by_id[alert.alert_id] = alert
            self._alert_ids_by_session.setdefault(alert.session_id, []).append(alert.alert_id)

            return alert

    def evaluate(self, session_id: str, metric_type: str, value: float) -> list:
        """
        Evaluate a session's ENABLED alerts watching metric_type
        against an observed value, triggering any whose threshold is
        crossed.

        Returns:
            The alerts newly triggered by this call

        Raises:
            ExecutionObservationAlertError: If session_id or
                metric_type is None or blank, or value is not
                numeric
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(metric_type, "metric type")

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExecutionObservationAlertError("Cannot evaluate alerts with a non-numeric value.")

        with self._lock:
            newly_triggered = []

            for alert_id in self._alert_ids_by_session.get(session_id, []):
                alert = self._alerts_by_id[alert_id]

                if not alert.enabled or alert.metric_type != metric_type:
                    continue

                if _COMPARISONS[alert.comparator](value, alert.threshold):
                    updated = replace(alert, triggered=True)
                    self._alerts_by_id[alert_id] = updated
                    newly_triggered.append(updated)

            return newly_triggered

    def active(self, session_id: str) -> list:
        """
        List a session's currently triggered alerts, in the order
        they were registered.

        Raises:
            ExecutionObservationAlertError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._alerts_by_id[alert_id]
                for alert_id in self._alert_ids_by_session.get(session_id, [])
                if self._alerts_by_id[alert_id].triggered
            ]

    def resolve(self, alert_id: str) -> ExecutionObservationAlert:
        """
        Clear a triggered alert's state, allowing it to trigger again
        on a future evaluate().

        Raises:
            ExecutionObservationAlertError: If alert_id is None or
                blank, or no alert is known under it
        """

        self._validate_id(alert_id, "alert ID")

        with self._lock:
            alert = self._resolve(alert_id)

            updated = replace(alert, triggered=False)
            self._alerts_by_id[alert_id] = updated

            return updated

    def _resolve(self, alert_id: str) -> ExecutionObservationAlert:
        alert = self._alerts_by_id.get(alert_id)

        if alert is None:
            raise ExecutionObservationAlertError(f"No alert is known under alert ID {alert_id!r}.")

        return alert

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationAlertError(f"Cannot use an empty or blank {field_name}.")
