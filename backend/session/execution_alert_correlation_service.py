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
    STATUS_OPEN as ALERT_STATUS_OPEN,
)

from .execution_observability_alert_correlation import (
    ExecutionObservabilityAlertCorrelation,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
)

from .execution_observability_alert_correlation_error import (
    ExecutionObservabilityAlertCorrelationError,
)


class ExecutionAlertCorrelationService:
    """
    Correlates related alerts, possibly spanning multiple runtimes,
    into a single observable event chain representing one underlying
    incident.

    Composes with an existing alert service (anything exposing
    `get(alert_id)` -> object with `.rule_id`, `.runtime_id`,
    `.triggered_at`, `.status`, matching ExecutionAlertService), used
    to read each alert's type, runtime, timing, and current status.
    Performs no alert triggering or resolution of its own, and never
    mutates the composed service.

    Behavior:
    - correlate() groups two or more alerts into a new ACTIVE
      correlation, but only alerts sharing the same rule_id (the same
      alert "type") are compatible; the earliest-triggered alert
      becomes root_alert_id; an alert already belonging to another
      still-ACTIVE correlation cannot join a second one
    - root() reports a correlation's root alert
    - alerts() reports every alert grouped into a correlation,
      earliest-triggered first
    - resolve() is idempotent: resolving an already-RESOLVED
      correlation simply returns it unchanged; resolving frees its
      member alerts to join a future correlation
    - Whenever this service reads a correlation (root(), alerts(),
      resolve()), it first checks the root alert's current status: if
      it is no longer OPEN, the correlation is resolved automatically,
      so resolving the root alert always resolves the correlation

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, alert_service):
        self._alert_service = alert_service
        self._correlations_by_id = {}
        self._correlation_id_by_alert = {}
        self._lock = RLock()

    def correlate(self, alert_ids) -> ExecutionObservabilityAlertCorrelation:
        """
        Group alert_ids into a new ACTIVE correlation.

        Raises:
            ExecutionObservabilityAlertCorrelationError: If alert_ids
                has fewer than two entries, contains a duplicate, any
                entry is unknown to the alert service, the alerts do
                not share the same rule_id, or any entry already
                belongs to another still-ACTIVE correlation
        """

        if not isinstance(alert_ids, (list, tuple)) or len(alert_ids) < 2:
            raise ExecutionObservabilityAlertCorrelationError(
                "Cannot correlate fewer than two alerts."
            )

        if len(set(alert_ids)) != len(alert_ids):
            raise ExecutionObservabilityAlertCorrelationError(
                "Cannot correlate the same alert twice within one correlation."
            )

        alerts = [self._resolve_alert(alert_id) for alert_id in alert_ids]

        rule_ids = {alert.rule_id for alert in alerts}

        if len(rule_ids) > 1:
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot correlate alerts of incompatible types: found rule IDs {sorted(rule_ids)!r}."
            )

        with self._lock:
            for alert in alerts:
                existing_id = self._correlation_id_by_alert.get(alert.alert_id)

                if existing_id is not None:
                    raise ExecutionObservabilityAlertCorrelationError(
                        f"Cannot correlate alert ID {alert.alert_id!r}: "
                        "it already belongs to another active correlation."
                    )

            ordered = sorted(alerts, key=lambda alert: alert.triggered_at)
            root_alert = ordered[0]

            correlation = ExecutionObservabilityAlertCorrelation(
                alert_ids=tuple(alert.alert_id for alert in ordered),
                runtime_ids=tuple(sorted({alert.runtime_id for alert in alerts})),
                root_alert_id=root_alert.alert_id,
                correlation_id=str(uuid4()),
                status=STATUS_ACTIVE,
                created_at=datetime.now(timezone.utc),
            )

            self._correlations_by_id[correlation.correlation_id] = correlation

            for alert in ordered:
                self._correlation_id_by_alert[alert.alert_id] = correlation.correlation_id

            return correlation

    def root(self, correlation_id: str):
        """
        The root alert of correlation_id.

        Raises:
            ExecutionObservabilityAlertCorrelationError: If
                correlation_id is None or blank, or no correlation is
                registered under it
        """

        self._validate_text(correlation_id, "correlation ID")

        with self._lock:
            correlation = self._resolve_correlation(correlation_id)
            correlation = self._synchronize(correlation)

        return self._alert_service.get(correlation.root_alert_id)

    def alerts(self, correlation_id: str) -> tuple:
        """
        Every alert grouped into correlation_id, earliest-triggered
        first.

        Raises:
            ExecutionObservabilityAlertCorrelationError: If
                correlation_id is None or blank, or no correlation is
                registered under it
        """

        self._validate_text(correlation_id, "correlation ID")

        with self._lock:
            correlation = self._resolve_correlation(correlation_id)
            correlation = self._synchronize(correlation)

        return tuple(self._alert_service.get(alert_id) for alert_id in correlation.alert_ids)

    def resolve(self, correlation_id: str) -> ExecutionObservabilityAlertCorrelation:
        """
        Resolve a correlation. Idempotent: resolving an
        already-RESOLVED correlation simply returns it unchanged.
        Resolving frees its member alerts to join a future
        correlation.

        Raises:
            ExecutionObservabilityAlertCorrelationError: If
                correlation_id is None or blank, or no correlation is
                registered under it
        """

        self._validate_text(correlation_id, "correlation ID")

        with self._lock:
            correlation = self._resolve_correlation(correlation_id)

            if correlation.status == STATUS_RESOLVED:
                return correlation

            return self._mark_resolved(correlation)

    def _synchronize(self, correlation: ExecutionObservabilityAlertCorrelation):
        if correlation.status == STATUS_RESOLVED:
            return correlation

        root_alert = self._alert_service.get(correlation.root_alert_id)

        if root_alert.status != ALERT_STATUS_OPEN:
            return self._mark_resolved(correlation)

        return correlation

    def _mark_resolved(
        self, correlation: ExecutionObservabilityAlertCorrelation
    ) -> ExecutionObservabilityAlertCorrelation:
        resolved = replace(correlation, status=STATUS_RESOLVED)
        self._correlations_by_id[correlation.correlation_id] = resolved

        for alert_id in correlation.alert_ids:
            if self._correlation_id_by_alert.get(alert_id) == correlation.correlation_id:
                del self._correlation_id_by_alert[alert_id]

        return resolved

    def _resolve_alert(self, alert_id: str):
        self._validate_text(alert_id, "alert ID")

        try:
            return self._alert_service.get(alert_id)
        except Exception as error:
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot correlate alert ID {alert_id!r}: it is unknown."
            ) from error

    def _resolve_correlation(self, correlation_id: str) -> ExecutionObservabilityAlertCorrelation:
        correlation = self._correlations_by_id.get(correlation_id)

        if correlation is None:
            raise ExecutionObservabilityAlertCorrelationError(
                f"No correlation is recorded under correlation ID {correlation_id!r}."
            )

        return correlation

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot use an empty or blank {field_name}."
            )
