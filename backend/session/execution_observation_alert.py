from dataclasses import (
    dataclass,
    field,
)

from uuid import uuid4

from .execution_observation_alert_error import (
    ExecutionObservationAlertError,
)

SUPPORTED_COMPARATORS = frozenset(
    {
        ">",
        "<",
        ">=",
        "<=",
    }
)


@dataclass(frozen=True)
class ExecutionObservationAlert:
    """
    Immutable snapshot of a configured alert, triggered when a
    session's observed metric value crosses a threshold.

    The alert is a value object only. It performs no evaluation of
    its own; registering an alert, evaluating it against observed
    values, listing active alerts, and resolving them is the
    responsibility of an execution observation alert service.

    Attributes:
        alert_id: The alert's unique identifier
        session_id: The identifier of the execution session the
            alert watches
        metric_type: Which metric type this alert watches, e.g.
            "LATENCY_MS"
        threshold: The numeric value the observed metric is compared
            against
        comparator: How the observed value is compared to threshold
            to decide whether the alert triggers, one of >, <, >=,
            or <=
        severity: How severe a trigger of this alert is, e.g. "LOW"
            or "CRITICAL"
        enabled: Whether this alert is evaluated at all; a disabled
            alert never triggers
        triggered: Whether this alert is currently in a triggered
            state
    """

    session_id: str

    metric_type: str

    threshold: float

    comparator: str

    severity: str

    enabled: bool = True

    alert_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    triggered: bool = False

    def __post_init__(self):
        self._require_text(self.alert_id, "alert ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.metric_type, "metric type")
        self._require_text(self.comparator, "comparator")
        self._require_text(self.severity, "severity")

        if self.comparator not in SUPPORTED_COMPARATORS:
            raise ExecutionObservationAlertError(
                f"Unsupported comparator {self.comparator!r}: expected one of {sorted(SUPPORTED_COMPARATORS)}."
            )

        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)):
            raise ExecutionObservationAlertError(
                "Cannot build an execution observation alert with a non-numeric threshold."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionObservationAlertError(
                "Cannot build an execution observation alert with a non-bool enabled."
            )

        if not isinstance(self.triggered, bool):
            raise ExecutionObservationAlertError(
                "Cannot build an execution observation alert with a non-bool triggered."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationAlertError(
                f"Cannot build an execution observation alert with an empty or blank {field_name}."
            )
