from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_shutdown_error import (
    ExecutionRuntimeShutdownError,
)

STATUS_STOPPING = "STOPPING"

STATUS_STOPPED = "STOPPED"

STATUSES = (
    STATUS_STOPPING,
    STATUS_STOPPED,
)


@dataclass(frozen=True)
class ExecutionRuntimeShutdown:
    """
    Immutable record of a single graceful shutdown of a runtime, from
    the moment it was requested to the moment (if any) it completed.

    The shutdown is a value object only. It performs no request/
    completion accounting of its own; requesting and completing
    shutdown, and releasing the runtime's resources, is the
    responsibility of an execution runtime shutdown service, which
    mutates completed_at and status on this same record via `replace`
    once shutdown finishes, rather than producing an unrelated new
    record.

    Attributes:
        shutdown_id: The shutdown's unique identifier
        runtime_id: The identifier of the runtime being shut down
        reason: Why the runtime is being shut down
        requested_at: When shutdown was requested
        completed_at: When shutdown completed, or None if it is still
            in progress
        status: The shutdown's current state, one of STATUSES
    """

    shutdown_id: str

    runtime_id: str

    reason: str

    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    completed_at: datetime = None

    status: str = STATUS_STOPPING

    def __post_init__(self):
        self._require_text(self.shutdown_id, "shutdown ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.reason, "reason")

        if self.requested_at is None or not isinstance(self.requested_at, datetime):
            raise ExecutionRuntimeShutdownError(
                "Cannot build an execution runtime shutdown with a non-datetime requested_at."
            )

        if self.completed_at is not None and not isinstance(self.completed_at, datetime):
            raise ExecutionRuntimeShutdownError(
                "Cannot build an execution runtime shutdown with a non-datetime completed_at."
            )

        if self.status not in STATUSES:
            raise ExecutionRuntimeShutdownError(
                f"Cannot build an execution runtime shutdown with an unknown status: {self.status!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeShutdownError(
                f"Cannot build an execution runtime shutdown with an empty or blank {field_name}."
            )
