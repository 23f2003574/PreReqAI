from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from uuid import uuid4

from .execution_observability_alert_error import (
    ExecutionObservabilityAlertError,
)

from .execution_observability_event import (
    SEVERITIES,
)

STATUS_OPEN = "OPEN"

STATUS_RESOLVED = "RESOLVED"

STATUSES = (
    STATUS_OPEN,
    STATUS_RESOLVED,
)


@dataclass(frozen=True)
class ExecutionObservabilityAlert:
    """
    Immutable record of a single alert instance triggered from an
    alert rule, persisted separately from the reusable rule itself.

    The alert is a value object only. It performs no lifecycle
    accounting of its own; triggering and resolving alerts is the
    responsibility of an execution alert service, which produces a
    new record for every transition rather than mutating an existing
    one.

    Attributes:
        alert_id: The alert's unique identifier
        rule_id: The identifier of the alert rule this alert was
            triggered from
        runtime_id: The identifier of the runtime the alert was
            triggered for
        severity: The alert's severity, one of SEVERITIES
        value: The metric value observed at the moment the alert was
            triggered
        status: The alert's current state, one of STATUSES
        triggered_at: When the alert was triggered
        resolved_at: When the alert was resolved, or None while it is
            still OPEN
    """

    rule_id: str

    runtime_id: str

    severity: str

    value: float

    alert_id: str = field(default_factory=lambda: str(uuid4()))

    status: str = STATUS_OPEN

    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    resolved_at: datetime = None

    def __post_init__(self):
        self._require_text(self.alert_id, "alert ID")
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.runtime_id, "runtime ID")

        if self.severity not in SEVERITIES:
            raise ExecutionObservabilityAlertError(
                f"Cannot build an execution observability alert with an unknown severity: {self.severity!r}."
            )

        if isinstance(self.value, bool) or not isinstance(self.value, Real):
            raise ExecutionObservabilityAlertError(
                f"Cannot build an execution observability alert with a non-numeric value: {self.value!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionObservabilityAlertError(
                f"Cannot build an execution observability alert with an unknown status: {self.status!r}."
            )

        if self.triggered_at is None or not isinstance(self.triggered_at, datetime):
            raise ExecutionObservabilityAlertError(
                "Cannot build an execution observability alert with a non-datetime triggered_at."
            )

        if self.resolved_at is not None and not isinstance(self.resolved_at, datetime):
            raise ExecutionObservabilityAlertError(
                "Cannot build an execution observability alert with a non-datetime resolved_at."
            )

        if self.status == STATUS_OPEN and self.resolved_at is not None:
            raise ExecutionObservabilityAlertError(
                "Cannot build an OPEN execution observability alert with a resolved_at."
            )

        if self.status == STATUS_RESOLVED and self.resolved_at is None:
            raise ExecutionObservabilityAlertError(
                "Cannot build a RESOLVED execution observability alert without a resolved_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertError(
                f"Cannot build an execution observability alert with an empty or blank {field_name}."
            )
