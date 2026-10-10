from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_scheduler_error import (
    ExecutionSchedulerError,
)


@dataclass(frozen=True)
class ExecutionScheduleDecision:
    """
    Immutable record of the outcome of running a job through the
    scheduler decision pipeline.

    The decision is a value object only, and is never mutated once
    created; it is the permanent account of what the pipeline decided
    and why. It is produced by an execution scheduler service, which
    reuses the queue, priority, dependency, capacity, reservation,
    retry, and failover components to reach it.

    Attributes:
        decision_id: The decision's unique identifier
        job_id: The identifier of the job the decision was made for
        scheduler_id: The scheduler the job was assigned to, or None
            if the job was not allowed to run
        allowed: Whether the job was allowed to run
        reason: Why the pipeline reached this decision
        created_at: When the decision was made
    """

    decision_id: str

    job_id: str

    scheduler_id: str

    allowed: bool

    reason: str

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.decision_id, "decision ID")
        self._require_text(self.job_id, "job ID")
        self._require_text(self.reason, "reason")

        if not isinstance(self.allowed, bool):
            raise ExecutionSchedulerError(
                "Cannot build an execution schedule decision with a non-bool allowed."
            )

        if self.allowed:
            if self.scheduler_id is None or not self.scheduler_id.strip():
                raise ExecutionSchedulerError(
                    "Cannot build an allowed execution schedule decision without a scheduler_id."
                )
        elif self.scheduler_id is not None:
            raise ExecutionSchedulerError(
                "Cannot build a disallowed execution schedule decision with a scheduler_id set."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionSchedulerError(
                "Cannot build an execution schedule decision with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulerError(
                f"Cannot build an execution schedule decision with an empty or blank {field_name}."
            )
