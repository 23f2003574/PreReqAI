from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from .execution_scheduling_retry_policy import (
    ExecutionSchedulingRetryPolicy,
)

from .execution_scheduling_retry_error import (
    ExecutionSchedulingRetryError,
)


class ExecutionSchedulingRetryService:
    """
    Makes scheduling retries adaptive instead of immediately
    requeueing failed jobs: each scope's ExecutionSchedulingRetryPolicy
    determines exponential backoff between attempts, and jobs that
    exhaust their attempts are handed off to the dead-letter queue
    instead of retried forever.

    Composes with an existing dead-letter service (anything exposing
    `move(job_id, reason)`, matching ExecutionDeadLetterService), used
    to isolate a job once its retries are exhausted.

    Behavior:
    - configure() sets the retry policy for a scope
    - retry() records one more attempt for a job against the scope's
      policy. A disabled policy rejects every attempt. An attempt that
      would exceed max_attempts instead hands the job off to the
      dead-letter service and returns None; every attempt before that
      returns the datetime of the next retry, backoff_seconds * 2 **
      (attempt_number - 1) after now
    - Once a job has been handed off, further retry() calls on it are
      rejected; it is no longer this service's to manage

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, dead_letter_service):
        self._dead_letter_service = dead_letter_service
        self._policies_by_scope = {}
        self._state_by_job = {}
        self._lock = RLock()

    def configure(self, scope_id: str, policy: ExecutionSchedulingRetryPolicy) -> ExecutionSchedulingRetryPolicy:
        """
        Set the retry policy for a scope.

        Raises:
            ExecutionSchedulingRetryError: If scope_id is None or
                blank, or policy is not an ExecutionSchedulingRetryPolicy
        """

        self._validate_text(scope_id, "scope ID")

        if not isinstance(policy, ExecutionSchedulingRetryPolicy):
            raise ExecutionSchedulingRetryError(
                "Cannot configure a scope with a policy that is not an ExecutionSchedulingRetryPolicy."
            )

        with self._lock:
            self._policies_by_scope[scope_id] = policy

            return policy

    def retry(self, job_id: str, scope_id: str):
        """
        Record one more retry attempt for job_id against scope_id's
        policy.

        Returns:
            The datetime of the next retry attempt, or None if this
            attempt exhausted the policy's max_attempts and job_id
            was handed off to the dead-letter service instead

        Raises:
            ExecutionSchedulingRetryError: If job_id or scope_id is
                None or blank, no policy is configured for scope_id,
                the policy is disabled, or job_id was already handed
                off to the dead-letter service
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(scope_id, "scope ID")

        with self._lock:
            policy = self._policies_by_scope.get(scope_id)

            if policy is None:
                raise ExecutionSchedulingRetryError(f"No retry policy is configured for scope ID {scope_id!r}.")

            if not policy.enabled:
                raise ExecutionSchedulingRetryError(
                    f"Cannot retry job ID {job_id!r}: the retry policy for scope ID {scope_id!r} is disabled."
                )

            state = self._state_by_job.get(job_id)

            if state is not None and state["exhausted"]:
                raise ExecutionSchedulingRetryError(
                    f"Cannot retry job ID {job_id!r}: it was already handed off to the dead-letter queue."
                )

            attempt_number = (state["attempts"] if state is not None else 0) + 1

            if attempt_number > policy.max_attempts:
                self._state_by_job[job_id] = {
                    "scope_id": scope_id,
                    "attempts": attempt_number - 1,
                    "next_retry_at": None,
                    "exhausted": True,
                }

                self._dead_letter_service.move(job_id, "max scheduling retry attempts exceeded")

                return None

            backoff = policy.backoff_seconds * (2 ** (attempt_number - 1))
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)

            self._state_by_job[job_id] = {
                "scope_id": scope_id,
                "attempts": attempt_number,
                "next_retry_at": next_retry_at,
                "exhausted": False,
            }

            return next_retry_at

    def next_retry(self, job_id: str):
        """
        The datetime of job_id's next scheduled retry, or None if it
        was handed off to the dead-letter service.

        Raises:
            ExecutionSchedulingRetryError: If job_id is None or
                blank, or job_id has never been retried
        """

        state = self._resolve(job_id)

        return state["next_retry_at"]

    def attempts(self, job_id: str) -> int:
        """
        How many retry attempts have been recorded for job_id.

        Raises:
            ExecutionSchedulingRetryError: If job_id is None or
                blank, or job_id has never been retried
        """

        state = self._resolve(job_id)

        return state["attempts"]

    def _resolve(self, job_id: str) -> dict:
        self._validate_text(job_id, "job ID")

        with self._lock:
            state = self._state_by_job.get(job_id)

            if state is None:
                raise ExecutionSchedulingRetryError(f"No retry attempts are recorded for job ID {job_id!r}.")

            return state

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulingRetryError(f"Cannot use an empty or blank {field_name}.")
