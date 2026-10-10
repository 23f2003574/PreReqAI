from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_recovery_result_error import (
    ExecutionRecoveryResultError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "COMPLETED",
        "FAILED",
    }
)


@dataclass(frozen=True)
class ExecutionRecoveryResult:
    """
    Immutable, auditable outcome of finalizing a session's recovery:
    either every required component succeeded, or the first one
    that did not.

    The result is a value object only. It performs no finalization
    of its own; checking a session's validation gate, unresolved
    conflicts, and recovery attempt, recording the outcome, and
    resetting a failed one is the responsibility of an execution
    recovery completion service.

    A session has at most one result at a time, so session_id is
    this record's natural key.

    Attributes:
        session_id: The identifier of the execution session this
            result is for
        checkpoint_id: The identifier of the checkpoint recovery was
            finalized against
        status: The outcome, one of COMPLETED or FAILED
        attempts: The recovery attempt number reached, or 0 if none
            was recorded
        completed_at: When recovery COMPLETED, or None if it FAILED
        failure_reason: Why recovery FAILED, or None if it COMPLETED
    """

    session_id: str

    checkpoint_id: str

    status: str

    attempts: int = 0

    completed_at: datetime | None = None

    failure_reason: str | None = None

    def __post_init__(self):
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionRecoveryResultError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.attempts, int) or isinstance(self.attempts, bool):
            raise ExecutionRecoveryResultError(
                "Cannot build an execution recovery result with a non-int attempts."
            )

        if self.attempts < 0:
            raise ExecutionRecoveryResultError(
                "Cannot build an execution recovery result with a negative attempts."
            )

        if self.status == "COMPLETED":
            if not isinstance(self.completed_at, datetime):
                raise ExecutionRecoveryResultError(
                    "Cannot build a COMPLETED execution recovery result with a non-datetime completed_at."
                )

            if self.failure_reason is not None:
                raise ExecutionRecoveryResultError(
                    "Cannot build a COMPLETED execution recovery result with a failure_reason set."
                )
        else:
            if self.completed_at is not None:
                raise ExecutionRecoveryResultError(
                    "Cannot build a FAILED execution recovery result with a completed_at set."
                )

            self._require_text(self.failure_reason, "failure reason")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryResultError(
                f"Cannot build an execution recovery result with an empty or blank {field_name}."
            )
