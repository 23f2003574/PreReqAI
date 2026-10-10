from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_trace_error import (
    ExecutionTraceError,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_COMPLETED = "COMPLETED"

STATUS_FAILED = "FAILED"

STATUS_CANCELLED = "CANCELLED"

TERMINAL_STATUSES = (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
)

STATUSES = (STATUS_ACTIVE,) + TERMINAL_STATUSES


@dataclass(frozen=True)
class ExecutionTrace:
    """
    Immutable record of a single span within a complete execution
    operation, optionally nested under a parent span.

    The trace is a value object only. It performs no lifecycle
    accounting of its own; starting and finishing traces is the
    responsibility of an execution trace service, which produces a
    new record for every transition rather than mutating an existing
    one.

    Attributes:
        trace_id: The trace's unique identifier
        runtime_id: The identifier of the runtime this trace was
            started within
        operation: The name of the operation this trace spans
        parent_span_id: The trace_id of the enclosing span, or None
            if this trace is a root span
        started_at: When the trace was started
        finished_at: When the trace was finished, or None while it is
            still ACTIVE
        status: The trace's current state, one of STATUSES
    """

    trace_id: str

    runtime_id: str

    operation: str

    parent_span_id: str = None

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    finished_at: datetime = None

    status: str = STATUS_ACTIVE

    def __post_init__(self):
        self._require_text(self.trace_id, "trace ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.operation, "operation")

        if self.parent_span_id is not None:
            self._require_text(self.parent_span_id, "parent span ID")

        if self.status not in STATUSES:
            raise ExecutionTraceError(
                f"Cannot build an execution trace with an unknown status: {self.status!r}."
            )

        if self.started_at is None or not isinstance(self.started_at, datetime):
            raise ExecutionTraceError(
                "Cannot build an execution trace with a non-datetime started_at."
            )

        if self.finished_at is not None and not isinstance(self.finished_at, datetime):
            raise ExecutionTraceError(
                "Cannot build an execution trace with a non-datetime finished_at."
            )

        if self.status == STATUS_ACTIVE and self.finished_at is not None:
            raise ExecutionTraceError(
                "Cannot build an ACTIVE execution trace with a finished_at."
            )

        if self.status in TERMINAL_STATUSES and self.finished_at is None:
            raise ExecutionTraceError(
                f"Cannot build a {self.status} execution trace without a finished_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionTraceError(
                f"Cannot build an execution trace with an empty or blank {field_name}."
            )
