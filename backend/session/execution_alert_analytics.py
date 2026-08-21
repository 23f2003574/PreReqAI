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

from .execution_alert_analytics_error import (
    ExecutionAlertAnalyticsError,
)


@dataclass(frozen=True)
class ExecutionAlertAnalytics:
    """
    Immutable runtime-level rollup of a runtime's alert history into
    actionable trends, computed at a point in time.

    The analytics record is a value object only. It performs no
    aggregation of its own; computing it from a runtime's recorded
    alerts is the responsibility of an execution alert analytics
    service, which produces a new record for every generate() call
    rather than mutating an existing one.

    Attributes:
        runtime_id: The identifier of the runtime this record
            describes
        total_alerts: How many alerts have ever been recorded for the
            runtime
        open_alerts: How many of those alerts are currently OPEN
        resolved_alerts: How many of those alerts are currently
            RESOLVED
        critical_count: How many of those alerts are ERROR severity
        recurrence_rate: The fraction of total_alerts that are repeat
            occurrences of an already-seen condition (0.0 to 1.0)
        generated_at: When this record was computed
    """

    runtime_id: str

    total_alerts: int

    open_alerts: int

    resolved_alerts: int

    critical_count: int

    recurrence_rate: float

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.runtime_id, "runtime ID")

        self._require_non_negative_int(self.total_alerts, "total_alerts")
        self._require_non_negative_int(self.open_alerts, "open_alerts")
        self._require_non_negative_int(self.resolved_alerts, "resolved_alerts")
        self._require_non_negative_int(self.critical_count, "critical_count")

        if self.open_alerts + self.resolved_alerts != self.total_alerts:
            raise ExecutionAlertAnalyticsError(
                "Cannot build execution alert analytics whose open_alerts and resolved_alerts "
                "do not add up to total_alerts."
            )

        if (
            isinstance(self.recurrence_rate, bool)
            or not isinstance(self.recurrence_rate, Real)
            or not (0.0 <= self.recurrence_rate <= 1.0)
        ):
            raise ExecutionAlertAnalyticsError(
                f"Cannot build execution alert analytics with a recurrence_rate outside [0.0, 1.0]: "
                f"{self.recurrence_rate!r}."
            )

        if self.generated_at is None or not isinstance(self.generated_at, datetime):
            raise ExecutionAlertAnalyticsError(
                "Cannot build execution alert analytics with a non-datetime generated_at."
            )

    @staticmethod
    def _require_non_negative_int(value, field_name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ExecutionAlertAnalyticsError(
                f"Cannot build execution alert analytics with a negative or non-integer {field_name}: "
                f"{value!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionAlertAnalyticsError(
                f"Cannot build execution alert analytics with an empty or blank {field_name}."
            )
