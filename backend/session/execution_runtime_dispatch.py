from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_dispatch_error import (
    ExecutionRuntimeDispatchError,
)

STATUS_DISPATCHED = "DISPATCHED"

STATUS_CANCELLED = "CANCELLED"

STATUSES = (
    STATUS_DISPATCHED,
    STATUS_CANCELLED,
)


@dataclass(frozen=True)
class ExecutionRuntimeDispatch:
    """
    Immutable record that an approved scheduled job has been handed
    off to a runtime target for execution.

    The dispatch is a value object only. It performs no dispatch
    accounting of its own; issuing and cancelling dispatches is the
    responsibility of an execution runtime dispatch service, which
    produces a new record for every transition rather than mutating
    an existing one.

    Attributes:
        dispatch_id: The dispatch's unique identifier
        job_id: The identifier of the job being dispatched
        scheduler_id: The identifier of the scheduler that approved
            the job to run
        target: The runtime destination the job is dispatched to
        status: The dispatch's current state, one of STATUSES
        dispatched_at: When the dispatch was issued
    """

    dispatch_id: str

    job_id: str

    scheduler_id: str

    target: str

    status: str = STATUS_DISPATCHED

    dispatched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.dispatch_id, "dispatch ID")
        self._require_text(self.job_id, "job ID")
        self._require_text(self.scheduler_id, "scheduler ID")
        self._require_text(self.target, "target")

        if self.status not in STATUSES:
            raise ExecutionRuntimeDispatchError(
                f"Cannot build an execution runtime dispatch with an unknown status: {self.status!r}."
            )

        if self.dispatched_at is None or not isinstance(self.dispatched_at, datetime):
            raise ExecutionRuntimeDispatchError(
                "Cannot build an execution runtime dispatch with a non-datetime dispatched_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeDispatchError(
                f"Cannot build an execution runtime dispatch with an empty or blank {field_name}."
            )
