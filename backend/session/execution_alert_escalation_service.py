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

from .execution_observability_escalation import (
    ExecutionObservabilityEscalation,
    LEVEL_CRITICAL,
    LEVEL_WARNING,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
)

from .execution_observability_escalation_error import (
    ExecutionObservabilityEscalationError,
)

_LEVEL_BY_SEVERITY = {
    "WARNING": LEVEL_WARNING,
    "ERROR": LEVEL_CRITICAL,
}


class ExecutionAlertEscalationService:
    """
    Escalates unresolved alerts whose severity requires intervention,
    and keeps escalation state in sync with the alert it was raised
    against.

    Composes with an existing alert service (anything exposing
    `get(alert_id)` -> object with `.status`, `.severity`, matching
    ExecutionAlertService), used to read an alert's current status
    and severity. Performs no alert triggering or resolution of its
    own, and never mutates the composed service.

    Behavior:
    - evaluate() reports the escalation level an OPEN alert's
      severity currently calls for, or None if its severity does not
      warrant escalation, or if the alert is not OPEN
    - escalate() raises a new ACTIVE escalation at that level, but
      only for an OPEN alert with an escalatable severity, and only
      if it has no other ACTIVE escalation (repeated escalation while
      one is already active is rejected)
    - level() reports the level of an alert's currently ACTIVE
      escalation, or None if it has none
    - resolve() is idempotent: resolving an already-RESOLVED
      escalation simply returns it unchanged
    - Whenever this service reads an alert's active escalation
      (level(), evaluate(), history()), it first checks the
      underlying alert: if the alert is no longer OPEN, its ACTIVE
      escalation (if any) is resolved automatically, so resolving an
      alert always resolves its active escalation
    - history() reports every escalation ever raised for an alert,
      oldest to newest

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, alert_service):
        self._alert_service = alert_service
        self._escalations_by_id = {}
        self._active_escalation_id_by_alert = {}
        self._lock = RLock()

    def evaluate(self, alert_id: str):
        """
        The escalation level alert_id's severity currently calls for,
        or None if it does not currently call for escalation.

        Raises:
            ExecutionObservabilityEscalationError: If alert_id is
                None or blank, or it is unknown to the alert service
        """

        self._validate_text(alert_id, "alert ID")

        alert = self._resolve_alert(alert_id)

        if alert.status != ALERT_STATUS_OPEN:
            return None

        return _LEVEL_BY_SEVERITY.get(alert.severity)

    def escalate(self, alert_id: str) -> ExecutionObservabilityEscalation:
        """
        Raise a new ACTIVE escalation for alert_id, at the level its
        severity calls for.

        Raises:
            ExecutionObservabilityEscalationError: If alert_id is
                None or blank, unknown to the alert service, not
                OPEN, its severity does not warrant escalation, or it
                already has an ACTIVE escalation
        """

        self._validate_text(alert_id, "alert ID")

        alert = self._resolve_alert(alert_id)

        if alert.status != ALERT_STATUS_OPEN:
            raise ExecutionObservabilityEscalationError(
                f"Cannot escalate alert ID {alert_id!r}: it is not open (status is {alert.status!r})."
            )

        level = _LEVEL_BY_SEVERITY.get(alert.severity)

        if level is None:
            raise ExecutionObservabilityEscalationError(
                f"Cannot escalate alert ID {alert_id!r}: "
                f"its severity {alert.severity!r} does not warrant escalation."
            )

        with self._lock:
            self._propagate_resolution(alert_id, alert)

            if alert_id in self._active_escalation_id_by_alert:
                raise ExecutionObservabilityEscalationError(
                    f"Cannot escalate alert ID {alert_id!r}: it already has an active escalation."
                )

            escalation = ExecutionObservabilityEscalation(
                alert_id=alert_id,
                level=level,
                reason=f"severity {alert.severity} requires intervention",
                escalation_id=str(uuid4()),
                escalated_at=datetime.now(timezone.utc),
                status=STATUS_ACTIVE,
            )

            self._escalations_by_id[escalation.escalation_id] = escalation
            self._active_escalation_id_by_alert[alert_id] = escalation.escalation_id

            return escalation

    def level(self, alert_id: str):
        """
        The level of alert_id's currently ACTIVE escalation, or None
        if it has none.

        Raises:
            ExecutionObservabilityEscalationError: If alert_id is
                None or blank, or it is unknown to the alert service
        """

        self._validate_text(alert_id, "alert ID")

        alert = self._resolve_alert(alert_id)

        with self._lock:
            self._propagate_resolution(alert_id, alert)

            escalation_id = self._active_escalation_id_by_alert.get(alert_id)

            if escalation_id is None:
                return None

            return self._escalations_by_id[escalation_id].level

    def resolve(self, escalation_id: str) -> ExecutionObservabilityEscalation:
        """
        Resolve an escalation. Idempotent: resolving an
        already-RESOLVED escalation simply returns it unchanged.

        Raises:
            ExecutionObservabilityEscalationError: If escalation_id
                is None or blank, or no escalation is registered
                under it
        """

        self._validate_text(escalation_id, "escalation ID")

        with self._lock:
            escalation = self._resolve_escalation(escalation_id)

            if escalation.status == STATUS_RESOLVED:
                return escalation

            resolved = replace(escalation, status=STATUS_RESOLVED)
            self._escalations_by_id[escalation_id] = resolved

            if self._active_escalation_id_by_alert.get(escalation.alert_id) == escalation_id:
                del self._active_escalation_id_by_alert[escalation.alert_id]

            return resolved

    def history(self, alert_id: str) -> tuple:
        """
        Every escalation ever raised for alert_id, oldest to newest.

        Raises:
            ExecutionObservabilityEscalationError: If alert_id is
                None or blank, or it is unknown to the alert service
        """

        self._validate_text(alert_id, "alert ID")

        alert = self._resolve_alert(alert_id)

        with self._lock:
            self._propagate_resolution(alert_id, alert)

            matching = [
                escalation
                for escalation in self._escalations_by_id.values()
                if escalation.alert_id == alert_id
            ]

        return tuple(sorted(matching, key=lambda escalation: escalation.escalated_at))

    def _propagate_resolution(self, alert_id: str, alert) -> None:
        if alert.status == ALERT_STATUS_OPEN:
            return

        escalation_id = self._active_escalation_id_by_alert.pop(alert_id, None)

        if escalation_id is None:
            return

        escalation = self._escalations_by_id[escalation_id]

        if escalation.status != STATUS_RESOLVED:
            self._escalations_by_id[escalation_id] = replace(escalation, status=STATUS_RESOLVED)

    def _resolve_alert(self, alert_id: str):
        try:
            return self._alert_service.get(alert_id)
        except Exception as error:
            raise ExecutionObservabilityEscalationError(
                f"Cannot resolve alert ID {alert_id!r}: it is unknown."
            ) from error

    def _resolve_escalation(self, escalation_id: str) -> ExecutionObservabilityEscalation:
        escalation = self._escalations_by_id.get(escalation_id)

        if escalation is None:
            raise ExecutionObservabilityEscalationError(
                f"No escalation is recorded under escalation ID {escalation_id!r}."
            )

        return escalation

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityEscalationError(f"Cannot use an empty or blank {field_name}.")
