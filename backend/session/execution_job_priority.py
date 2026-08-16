from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_job_priority_error import (
    ExecutionJobPriorityError,
)

PRIORITY_LOW = "LOW"

PRIORITY_NORMAL = "NORMAL"

PRIORITY_HIGH = "HIGH"

PRIORITY_CRITICAL = "CRITICAL"

PRIORITIES = (
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    PRIORITY_HIGH,
    PRIORITY_CRITICAL,
)

PRIORITY_RANK = {
    PRIORITY_LOW: 0,
    PRIORITY_NORMAL: 1,
    PRIORITY_HIGH: 2,
    PRIORITY_CRITICAL: 3,
}


@dataclass(frozen=True)
class ExecutionJobPriority:
    """
    Immutable record of the scheduling priority assigned to an
    execution job.

    The priority is a value object only. It performs no scheduling of
    its own; assigning and updating priority, and ordering jobs by
    it, is the responsibility of an execution job priority service,
    which produces a new record for every update rather than mutating
    an existing one.

    Attributes:
        job_id: The identifier of the execution job this priority
            applies to
        priority: The job's current priority, one of PRIORITIES
        updated_at: When this priority was assigned. Also used to
            break ties, FIFO, between jobs sharing the same priority
    """

    job_id: str

    priority: str

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.job_id, "job ID")

        if self.priority not in PRIORITIES:
            raise ExecutionJobPriorityError(
                f"Cannot build an execution job priority with an unknown priority: {self.priority!r}."
            )

        if self.updated_at is None or not isinstance(self.updated_at, datetime):
            raise ExecutionJobPriorityError(
                "Cannot build an execution job priority with a non-datetime updated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionJobPriorityError(
                f"Cannot build an execution job priority with an empty or blank {field_name}."
            )
