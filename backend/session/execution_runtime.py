from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_startup_error import (
    ExecutionRuntimeStartupError,
)

STATUS_RUNNING = "RUNNING"

STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_RUNNING,
    STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionRuntime:
    """
    Immutable record that a dispatched job has been initialized into
    a running execution.

    The runtime is a value object only. It performs no startup
    accounting of its own; starting and failing runtimes is the
    responsibility of an execution runtime startup service, which
    produces a new record for every transition rather than mutating
    an existing one.

    Attributes:
        runtime_id: The runtime's unique identifier
        dispatch_id: The identifier of the dispatch this runtime was
            started from
        session_id: The identifier of the session this runtime is
            running within
        status: The runtime's current state, one of STATUSES
        started_at: When the runtime was started
    """

    runtime_id: str

    dispatch_id: str

    session_id: str

    status: str = STATUS_RUNNING

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.dispatch_id, "dispatch ID")
        self._require_text(self.session_id, "session ID")

        if self.status not in STATUSES:
            raise ExecutionRuntimeStartupError(
                f"Cannot build an execution runtime with an unknown status: {self.status!r}."
            )

        if self.started_at is None or not isinstance(self.started_at, datetime):
            raise ExecutionRuntimeStartupError(
                "Cannot build an execution runtime with a non-datetime started_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeStartupError(
                f"Cannot build an execution runtime with an empty or blank {field_name}."
            )
