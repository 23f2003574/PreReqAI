from dataclasses import (
    dataclass,
)

from .execution_artifact_distribution_retry_error import (
    ExecutionArtifactDistributionRetryError,
)


@dataclass(frozen=True)
class DistributionRetryPolicy:
    """
    Immutable configuration governing how many times a failed
    distribution delivery may be retried and how long to wait
    between attempts.

    The policy is a value object only. It performs no retrying of
    its own; configuring the active policy and retrying deliveries
    under it is the responsibility of an execution artifact
    distribution retry service.

    Attributes:
        policy_id: The policy's unique identifier
        max_attempts: The maximum number of delivery attempts a
            delivery may accumulate before it may no longer be
            retried
        backoff_seconds: The base number of seconds to wait before a
            retry, used to compute each attempt's deterministic
            backoff
        enabled: Whether the policy currently permits retries
    """

    policy_id: str

    max_attempts: int

    backoff_seconds: int

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")

        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise ExecutionArtifactDistributionRetryError(
                "Cannot build a retry policy with a non-integer max_attempts."
            )

        if self.max_attempts < 1:
            raise ExecutionArtifactDistributionRetryError(
                "Cannot build a retry policy with a max_attempts below 1."
            )

        if not isinstance(self.backoff_seconds, int) or isinstance(self.backoff_seconds, bool):
            raise ExecutionArtifactDistributionRetryError(
                "Cannot build a retry policy with a non-integer backoff_seconds."
            )

        if self.backoff_seconds < 0:
            raise ExecutionArtifactDistributionRetryError(
                "Cannot build a retry policy with a negative backoff_seconds."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionArtifactDistributionRetryError(
                "Cannot build a retry policy with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionRetryError(
                f"Cannot build a retry policy with an empty or blank {field_name}."
            )
