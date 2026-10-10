from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_dead_letter_error import (
    ExecutionDeadLetterError,
)


@dataclass(frozen=True)
class ExecutionDeadLetterJob:
    """
    Immutable record of a job that was pulled out of normal
    scheduling after repeatedly failing, so it stops being retried
    indefinitely.

    The record is a value object only, and is never mutated once
    created; it is the permanent, original account of why and when a
    job was moved. Retrying or discarding it is tracked separately by
    an execution dead-letter service, and never changes the fields
    recorded here.

    Attributes:
        dead_letter_id: The record's unique identifier
        job_id: The identifier of the job that was moved
        failure_count: How many scheduling failures the job had
            accumulated at the moment it was moved
        reason: Why the job was moved
        moved_at: When the job was moved
    """

    dead_letter_id: str

    job_id: str

    failure_count: int

    reason: str

    moved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.dead_letter_id, "dead-letter ID")
        self._require_text(self.job_id, "job ID")
        self._require_text(self.reason, "reason")

        if not isinstance(self.failure_count, int) or isinstance(self.failure_count, bool):
            raise ExecutionDeadLetterError(
                "Cannot build an execution dead-letter job with a non-int failure_count."
            )

        if self.failure_count < 1:
            raise ExecutionDeadLetterError(
                "Cannot build an execution dead-letter job with a failure_count below 1."
            )

        if self.moved_at is None or not isinstance(self.moved_at, datetime):
            raise ExecutionDeadLetterError(
                "Cannot build an execution dead-letter job with a non-datetime moved_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionDeadLetterError(
                f"Cannot build an execution dead-letter job with an empty or blank {field_name}."
            )
