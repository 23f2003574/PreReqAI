from dataclasses import dataclass
from datetime import datetime

# Metric names emitted to an external telemetry sink. Named and united the
# way ExecutionMetric already expects ("latency_ms" / "ms"), so a sample from
# a tool call sits alongside runtime samples without special handling.
DURATION_METRIC = "tool_execution_duration_ms"
DURATION_UNIT = "ms"
ATTEMPTS_METRIC = "tool_execution_attempts"
ATTEMPTS_UNIT = "count"


class InvalidToolMetricError(ValueError):
    """Raised when an execution cannot be measured."""


class UnknownToolMetricError(KeyError):
    """Raised when looking up an execution_id with no recorded metrics."""


@dataclass(frozen=True)
class LLMToolExecutionMetrics:
    """One immutable measurement of a finished tool execution.

    Shaped like the codebase's other telemetry records (LLMUsageRecord,
    ExecutionMetric): an id, the scope it belongs to, the numbers, and when
    it was taken. Never mutated -- record() produces a new one per
    execution.

    What is deliberately absent is the point: there is no field for the
    tool's arguments, its output, or its error text. Any of the three can
    carry a credential, and none is needed to answer how long a call took,
    how many attempts it needed, or how it ended. Metrics are counts and
    durations, not payloads.

    Attributes:
        execution_id: The execution measured
        duration: Wall-clock seconds from started_at to completed_at
        attempts: How many attempts the logical call took (1 when it was
            not retried)
        status: The execution's own terminal status -- SUCCEEDED, FAILED,
            DENIED, REJECTED, TIMED_OUT or CANCELLED
        tool_name: The tool invoked
    """

    metric_id: str
    execution_id: str
    duration: float
    attempts: int
    status: str
    tool_name: str
    recorded_at: datetime

    @property
    def duration_ms(self) -> float:
        return self.duration * 1000.0
