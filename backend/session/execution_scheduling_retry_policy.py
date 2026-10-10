from dataclasses import (
    dataclass,
)

from numbers import (
    Real,
)

from .execution_scheduling_retry_error import (
    ExecutionSchedulingRetryError,
)


@dataclass(frozen=True)
class ExecutionSchedulingRetryPolicy:
    """
    Immutable definition of how a scope retries jobs that fail
    scheduling: how many times to try, and how long to wait between
    tries.

    The policy is a value object only. It performs no retry
    bookkeeping of its own; applying it to a job's retry attempts is
    the responsibility of an execution scheduling retry service.

    Attributes:
        policy_id: The policy's unique identifier
        max_attempts: The maximum number of retry attempts allowed
            before a job is handed off to the dead-letter queue.
            Must be at least 1
        backoff_seconds: The base delay, in seconds, before the first
            retry; each subsequent retry doubles it. Must be positive
        enabled: Whether the policy currently permits retries. A
            disabled policy rejects every retry attempt
    """

    policy_id: str

    max_attempts: int

    backoff_seconds: float

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")

        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise ExecutionSchedulingRetryError(
                "Cannot build an execution scheduling retry policy with a non-int max_attempts."
            )

        if self.max_attempts < 1:
            raise ExecutionSchedulingRetryError(
                "Cannot build an execution scheduling retry policy with a max_attempts below 1."
            )

        if not isinstance(self.backoff_seconds, Real) or isinstance(self.backoff_seconds, bool):
            raise ExecutionSchedulingRetryError(
                "Cannot build an execution scheduling retry policy with a non-numeric backoff_seconds."
            )

        if self.backoff_seconds <= 0:
            raise ExecutionSchedulingRetryError(
                "Cannot build an execution scheduling retry policy with a non-positive backoff_seconds."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionSchedulingRetryError(
                "Cannot build an execution scheduling retry policy with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulingRetryError(
                f"Cannot build an execution scheduling retry policy with an empty or blank {field_name}."
            )
