from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_recovery_attempt_error import (
    ExecutionRecoveryAttemptError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "IN_PROGRESS",
        "SUCCEEDED",
        "FAILED",
    }
)


@dataclass(frozen=True)
class ExecutionRecoveryAttempt:
    """
    Immutable record of one attempt to recover a session by way of a
    resume plan.

    The attempt is a value object only. It performs no retry logic
    of its own; starting an attempt, finishing it, retrying after a
    failure, and looking up a plan's history is the responsibility
    of an execution recovery retry service.

    Attributes:
        attempt_id: The attempt's unique identifier
        plan_id: The identifier of the resume plan this attempt is
            for
        attempt_number: This attempt's 1-based position in its
            plan's attempt history
        status: The attempt's current status, one of IN_PROGRESS,
            SUCCEEDED, or FAILED
        started_at: When this attempt started
        finished_at: When this attempt finished, or None while it is
            still IN_PROGRESS
    """

    plan_id: str

    attempt_number: int

    status: str = "IN_PROGRESS"

    attempt_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    finished_at: datetime | None = None

    def __post_init__(self):
        self._require_text(self.attempt_id, "attempt ID")
        self._require_text(self.plan_id, "plan ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionRecoveryAttemptError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.attempt_number, int) or isinstance(self.attempt_number, bool):
            raise ExecutionRecoveryAttemptError(
                "Cannot build an execution recovery attempt with a non-int attempt_number."
            )

        if self.attempt_number < 1:
            raise ExecutionRecoveryAttemptError(
                "Cannot build an execution recovery attempt with an attempt_number below 1."
            )

        if not isinstance(self.started_at, datetime):
            raise ExecutionRecoveryAttemptError(
                "Cannot build an execution recovery attempt with a non-datetime started_at."
            )

        if self.status == "IN_PROGRESS":
            if self.finished_at is not None:
                raise ExecutionRecoveryAttemptError(
                    "Cannot build an execution recovery attempt that is IN_PROGRESS with a finished_at set."
                )
        else:
            if not isinstance(self.finished_at, datetime):
                raise ExecutionRecoveryAttemptError(
                    f"Cannot build a {self.status} execution recovery attempt with a non-datetime finished_at."
                )

            if self.finished_at < self.started_at:
                raise ExecutionRecoveryAttemptError(
                    "Cannot build an execution recovery attempt with a finished_at before started_at."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryAttemptError(
                f"Cannot build an execution recovery attempt with an empty or blank {field_name}."
            )
