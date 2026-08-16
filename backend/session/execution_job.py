from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_job_error import (
    ExecutionJobError,
)

STATUS_QUEUED = "QUEUED"

STATUS_READY = "READY"

STATUS_CANCELLED = "CANCELLED"

STATUSES = (
    STATUS_QUEUED,
    STATUS_READY,
    STATUS_CANCELLED,
)


@dataclass(frozen=True)
class ExecutionJob:
    """
    Immutable record of an execution job waiting to be scheduled.

    The job is a value object only. It performs no queueing of its
    own; enqueueing, dequeueing, and cancellation are the
    responsibility of an execution job queue service, which produces
    a new record for every transition rather than mutating an
    existing one.

    Attributes:
        job_id: The job's unique identifier
        session_id: The identifier of the execution session this job
            belongs to
        payload: Arbitrary job-specific data to be handed to the
            scheduler once the job is dequeued
        status: The job's current state, one of STATUSES
        queued_at: When the job was queued
    """

    job_id: str

    session_id: str

    payload: object

    status: str = STATUS_QUEUED

    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.job_id, "job ID")
        self._require_text(self.session_id, "session ID")

        if self.status not in STATUSES:
            raise ExecutionJobError(
                f"Cannot build an execution job with an unknown status: {self.status!r}."
            )

        if self.queued_at is None or not isinstance(self.queued_at, datetime):
            raise ExecutionJobError(
                "Cannot build an execution job with a non-datetime queued_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionJobError(
                f"Cannot build an execution job with an empty or blank {field_name}."
            )
