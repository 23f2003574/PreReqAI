from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_event_error import (
    ExecutionObservabilityEventError,
)

SEVERITY_DEBUG = "DEBUG"

SEVERITY_INFO = "INFO"

SEVERITY_WARNING = "WARNING"

SEVERITY_ERROR = "ERROR"

SEVERITIES = (
    SEVERITY_DEBUG,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
)


@dataclass(frozen=True)
class ExecutionObservabilityEvent:
    """
    Immutable record of a single lifecycle or operational event
    raised by a runtime, for execution tracing.

    The event is a value object only. It performs no recording,
    retrieval, or filtering of its own; that is the responsibility of
    an execution event service, which produces a new record for
    every occurrence rather than mutating an existing one.

    Attributes:
        runtime_id: The identifier of the runtime the event was
            raised against
        event_type: What kind of event this is, e.g. "STARTED" or
            "TASK_FAILED"
        severity: The event's severity, one of SEVERITIES
        payload: Arbitrary event-specific data
        event_id: The event's unique identifier
        occurred_at: When the event occurred
    """

    runtime_id: str

    event_type: str

    severity: str

    payload: object

    event_id: str = field(default_factory=lambda: str(uuid4()))

    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.event_id, "event ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.event_type, "event type")

        if self.severity not in SEVERITIES:
            raise ExecutionObservabilityEventError(
                f"Cannot build an execution observability event with an unknown severity: {self.severity!r}."
            )

        if not isinstance(self.occurred_at, datetime):
            raise ExecutionObservabilityEventError(
                "Cannot build an execution observability event with a non-datetime occurred_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityEventError(
                f"Cannot build an execution observability event with an empty or blank {field_name}."
            )
