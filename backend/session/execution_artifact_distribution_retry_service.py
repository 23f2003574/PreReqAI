from threading import (
    RLock,
)

from .distribution_retry_policy import (
    DistributionRetryPolicy,
)

from .execution_artifact_distribution_retry_error import (
    ExecutionArtifactDistributionRetryError,
)


class ExecutionArtifactDistributionRetryService:
    """
    Governs whether and when a failed distribution delivery may be
    retried, under a single, currently configured retry policy, using
    an existing execution artifact distribution delivery service as
    the source of truth for a delivery's status and attempt count.

    The service's responsibility is retry policy bookkeeping and
    eligibility only. It does not attempt delivery itself; retry()
    delegates the actual attempt to the delivery service once
    eligibility is confirmed.

    Behavior:
    - configure() replaces the active policy; only one policy is
      active at a time
    - A delivery is only ever retried while it is FAILED: a PENDING
      delivery has nothing to retry and a DELIVERED delivery is
      already complete
    - A delivery that has reached the active policy's max_attempts
      may no longer be retried
    - A disabled policy rejects every retry
    - next_attempt() computes each attempt's backoff deterministically
      as backoff_seconds * 2 ** (attempts - 1): the wait doubles with
      each prior attempt

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_distribution_delivery_service):
        """
        Args:
            execution_artifact_distribution_delivery_service: The
                service used to look up a delivery's current status
                and attempt count, and to perform the actual retry.
                Any object exposing `status(delivery_id)` (returning
                an object with `.status` and `.attempts`) and
                `retry(delivery_id)`, each raising if the delivery is
                unknown, is accepted
        """

        self._execution_artifact_distribution_delivery_service = execution_artifact_distribution_delivery_service
        self._policy = None
        self._lock = RLock()

    def configure(self, policy: DistributionRetryPolicy) -> DistributionRetryPolicy:
        """
        Replace the active retry policy.

        Raises:
            ExecutionArtifactDistributionRetryError: If policy is not
                a DistributionRetryPolicy
        """

        if not isinstance(policy, DistributionRetryPolicy):
            raise ExecutionArtifactDistributionRetryError(
                "Cannot configure an invalid retry policy: policy must be a DistributionRetryPolicy."
            )

        with self._lock:
            self._policy = policy

            return policy

    def can_retry(self, delivery_id: str) -> bool:
        """
        Check whether a delivery is currently eligible for retry
        under the active policy: FAILED, under max_attempts, with the
        policy enabled.

        Raises:
            ExecutionArtifactDistributionRetryError: If delivery_id is
                None or blank, no policy has been configured, or the
                delivery is unknown
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            policy = self._ensure_policy()
            delivery = self._delivery_status(delivery_id)

            return policy.enabled and delivery.status == "FAILED" and delivery.attempts < policy.max_attempts

    def next_attempt(self, delivery_id: str) -> int:
        """
        Compute the number of seconds to wait before a delivery's
        next attempt, deterministically from its current attempt
        count and the active policy's backoff_seconds.

        Raises:
            ExecutionArtifactDistributionRetryError: If delivery_id is
                None or blank, no policy has been configured, or the
                delivery is unknown
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            policy = self._ensure_policy()
            delivery = self._delivery_status(delivery_id)

            return policy.backoff_seconds * (2 ** max(delivery.attempts - 1, 0))

    def retry(self, delivery_id: str):
        """
        Retry a failed delivery, if the active policy allows it.

        Raises:
            ExecutionArtifactDistributionRetryError: If delivery_id is
                None or blank, no policy has been configured, the
                delivery is unknown, the policy is disabled, the
                delivery is not FAILED, or the delivery has reached
                the policy's max_attempts
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            policy = self._ensure_policy()
            delivery = self._delivery_status(delivery_id)

            if not policy.enabled:
                raise ExecutionArtifactDistributionRetryError(
                    f"Cannot retry delivery ID {delivery_id!r}: retry policy {policy.policy_id!r} is disabled."
                )

            if delivery.status != "FAILED":
                raise ExecutionArtifactDistributionRetryError(
                    f"Cannot retry delivery ID {delivery_id!r}: it is {delivery.status}, not FAILED."
                )

            if delivery.attempts >= policy.max_attempts:
                raise ExecutionArtifactDistributionRetryError(
                    f"Cannot retry delivery ID {delivery_id!r}: it has reached the policy's max_attempts of "
                    f"{policy.max_attempts}."
                )

            return self._execution_artifact_distribution_delivery_service.retry(delivery_id)

    def _ensure_policy(self) -> DistributionRetryPolicy:
        if self._policy is None:
            raise ExecutionArtifactDistributionRetryError("No retry policy has been configured.")

        return self._policy

    def _delivery_status(self, delivery_id: str):
        try:
            return self._execution_artifact_distribution_delivery_service.status(delivery_id)
        except Exception as error:
            raise ExecutionArtifactDistributionRetryError(
                f"No delivery is known under delivery ID {delivery_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionRetryError(f"Cannot use an empty or blank {field_name}.")
