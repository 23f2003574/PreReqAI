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

from .execution_metric_error import (
    ExecutionMetricError,
)


@dataclass(frozen=True)
class ExecutionMetric:
    """
    Immutable record of a single runtime performance or resource
    usage measurement.

    The metric is a value object only. It performs no recording,
    retrieval, or aggregation of its own; that is the responsibility
    of an execution metrics service, which produces a new record for
    every sample rather than mutating an existing one.

    Attributes:
        runtime_id: The identifier of the runtime the metric was
            recorded against
        name: What the metric measures, e.g. "latency_ms" or
            "memory_mb"
        value: The metric's numeric value
        unit: The unit value is expressed in, e.g. "ms" or "mb"
        metric_id: The metric's unique identifier
        recorded_at: When this metric was recorded
    """

    runtime_id: str

    name: str

    value: float

    unit: str

    metric_id: str = field(default_factory=lambda: str(uuid4()))

    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.metric_id, "metric ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.name, "name")
        self._require_text(self.unit, "unit")

        if isinstance(self.value, bool) or not isinstance(self.value, Real):
            raise ExecutionMetricError(
                "Cannot build an execution metric with a non-numeric value."
            )

        if not isinstance(self.recorded_at, datetime):
            raise ExecutionMetricError(
                "Cannot build an execution metric with a non-datetime recorded_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionMetricError(
                f"Cannot build an execution metric with an empty or blank {field_name}."
            )
