from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_summary_error import (
    ExecutionObservabilitySummaryError,
)


@dataclass(frozen=True)
class ExecutionObservabilitySummary:
    """
    Immutable runtime-level rollup of previously recorded metrics and
    events, computed at a point in time.

    The summary is a value object only. It performs no aggregation of
    its own; computing it from a runtime's recorded metrics and
    events is the responsibility of an execution observability
    aggregation service, which produces a new summary for every
    generate() call rather than mutating an existing one.

    Attributes:
        runtime_id: The identifier of the runtime this summary
            describes
        metrics: Per metric name: {"mean": float, "unit": str,
            "count": int}
        event_counts: {"by_type": {event_type: count}, "by_severity":
            {severity: count}}
        error_count: The number of ERROR-severity events recorded for
            the runtime
        summary_id: The summary's unique identifier
        generated_at: When this summary was computed
    """

    runtime_id: str

    metrics: dict

    event_counts: dict

    error_count: int

    summary_id: str = field(default_factory=lambda: str(uuid4()))

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.summary_id, "summary ID")
        self._require_text(self.runtime_id, "runtime ID")

        if not isinstance(self.metrics, dict):
            raise ExecutionObservabilitySummaryError(
                "Cannot build an execution observability summary with a non-dict metrics."
            )

        if not isinstance(self.event_counts, dict):
            raise ExecutionObservabilitySummaryError(
                "Cannot build an execution observability summary with a non-dict event_counts."
            )

        if isinstance(self.error_count, bool) or not isinstance(self.error_count, int) or self.error_count < 0:
            raise ExecutionObservabilitySummaryError(
                f"Cannot build an execution observability summary with a negative or non-integer "
                f"error_count: {self.error_count!r}."
            )

        if not isinstance(self.generated_at, datetime):
            raise ExecutionObservabilitySummaryError(
                "Cannot build an execution observability summary with a non-datetime generated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilitySummaryError(
                f"Cannot build an execution observability summary with an empty or blank {field_name}."
            )
