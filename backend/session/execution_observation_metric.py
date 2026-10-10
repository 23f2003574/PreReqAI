from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observation_metric_error import (
    ExecutionObservationMetricError,
)


@dataclass(frozen=True)
class ExecutionObservationMetric:
    """
    Immutable record of a single execution observation metric,
    aggregated from execution observation events into a runtime
    measurement.

    The metric is a value object only. It performs no recording or
    aggregation of its own; recording, retrieving, and aggregating
    metrics is the responsibility of an execution observation metric
    service.

    Attributes:
        metric_id: The metric's unique identifier
        session_id: The identifier of the execution session the
            metric was recorded against
        metric_type: What kind of metric this is, e.g. "LATENCY_MS"
            or "TOKENS_USED"
        value: The metric's numeric value
        recorded_at: When this metric was recorded
    """

    session_id: str

    metric_type: str

    value: float

    metric_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.metric_id, "metric ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.metric_type, "metric type")

        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ExecutionObservationMetricError(
                "Cannot build an execution observation metric with a non-numeric value."
            )

        if not isinstance(self.recorded_at, datetime):
            raise ExecutionObservationMetricError(
                "Cannot build an execution observation metric with a non-datetime recorded_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationMetricError(
                f"Cannot build an execution observation metric with an empty or blank {field_name}."
            )
