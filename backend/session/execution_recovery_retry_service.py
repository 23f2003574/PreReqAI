from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_recovery_attempt_error import (
    ExecutionRecoveryAttemptError,
)

from .execution_recovery_attempt import (
    ExecutionRecoveryAttempt,
)

FINISHABLE_STATUSES = frozenset(
    {
        "SUCCEEDED",
        "FAILED",
    }
)


class ExecutionRecoveryRetryService:
    """
    Tracks attempts to recover a session by way of a resume plan,
    allowing a failed attempt to be retried without creating a
    duplicate resume plan.

    Resume plans are assumed to already exist elsewhere; plan_id is
    used only as an opaque key to group a plan's attempts.

    Behavior:
    - start() records a plan's first attempt; a plan may only have
      one attempt in flight, and once resolved, at most one that is
      not FAILED
    - finish() records an attempt's outcome, SUCCEEDED or FAILED
    - retry() records a new attempt for a plan, but only if its
      latest attempt FAILED; a SUCCEEDED attempt is terminal, so no
      further attempt (via start() or retry()) is ever recorded for
      that plan again
    - attempts() returns a plan's full attempt history, in the order
      attempts were started
    - latest() returns a plan's most recent attempt, or None if it
      has none

    Attempt numbers are assigned sequentially per plan, starting at
    1, and are never reused.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._attempts_by_id = {}
        self._attempt_ids_by_plan = {}
        self._lock = RLock()

    def start(self, plan_id: str) -> ExecutionRecoveryAttempt:
        """
        Record a plan's first attempt.

        Raises:
            ExecutionRecoveryAttemptError: If plan_id is None or
                blank, or the plan already has an attempt recorded
        """

        self._validate_id(plan_id, "plan ID")

        with self._lock:
            if self._attempt_ids_by_plan.get(plan_id):
                raise ExecutionRecoveryAttemptError(
                    f"Plan ID {plan_id!r} already has a recorded attempt; use retry() instead of start()."
                )

            return self._record(plan_id)

    def finish(self, attempt_id: str, status: str) -> ExecutionRecoveryAttempt:
        """
        Record an attempt's outcome.

        Raises:
            ExecutionRecoveryAttemptError: If attempt_id is None or
                blank, status is not SUCCEEDED or FAILED, no attempt
                is known under attempt_id, or it is not IN_PROGRESS
        """

        self._validate_id(attempt_id, "attempt ID")

        if status not in FINISHABLE_STATUSES:
            raise ExecutionRecoveryAttemptError(
                f"Cannot finish an attempt with status {status!r}: expected one of {sorted(FINISHABLE_STATUSES)}."
            )

        with self._lock:
            attempt = self._resolve(attempt_id)

            if attempt.status != "IN_PROGRESS":
                raise ExecutionRecoveryAttemptError(
                    f"Cannot finish attempt ID {attempt_id!r}: it is {attempt.status}, not IN_PROGRESS."
                )

            updated = replace(attempt, status=status, finished_at=datetime.now(timezone.utc))
            self._attempts_by_id[attempt_id] = updated

            return updated

    def retry(self, plan_id: str) -> ExecutionRecoveryAttempt:
        """
        Record a new attempt for a plan whose latest attempt FAILED.

        Raises:
            ExecutionRecoveryAttemptError: If plan_id is None or
                blank, the plan has no recorded attempt, or its
                latest attempt is not FAILED
        """

        self._validate_id(plan_id, "plan ID")

        with self._lock:
            latest = self.latest(plan_id)

            if latest is None:
                raise ExecutionRecoveryAttemptError(
                    f"Plan ID {plan_id!r} has no recorded attempt; use start() instead of retry()."
                )

            if latest.status != "FAILED":
                raise ExecutionRecoveryAttemptError(
                    f"Cannot retry plan ID {plan_id!r}: its latest attempt is {latest.status}, not FAILED."
                )

            return self._record(plan_id)

    def attempts(self, plan_id: str) -> tuple:
        """
        List a plan's full attempt history, in the order attempts
        were started.

        Raises:
            ExecutionRecoveryAttemptError: If plan_id is None or
                blank
        """

        self._validate_id(plan_id, "plan ID")

        with self._lock:
            return tuple(
                self._attempts_by_id[attempt_id] for attempt_id in self._attempt_ids_by_plan.get(plan_id, [])
            )

    def latest(self, plan_id: str) -> ExecutionRecoveryAttempt | None:
        """
        Look up a plan's most recent attempt.

        Raises:
            ExecutionRecoveryAttemptError: If plan_id is None or
                blank
        """

        self._validate_id(plan_id, "plan ID")

        with self._lock:
            attempt_ids = self._attempt_ids_by_plan.get(plan_id)

            return self._attempts_by_id[attempt_ids[-1]] if attempt_ids else None

    def _record(self, plan_id: str) -> ExecutionRecoveryAttempt:
        attempt_number = len(self._attempt_ids_by_plan.get(plan_id, [])) + 1

        attempt = ExecutionRecoveryAttempt(plan_id=plan_id, attempt_number=attempt_number)

        self._attempts_by_id[attempt.attempt_id] = attempt
        self._attempt_ids_by_plan.setdefault(plan_id, []).append(attempt.attempt_id)

        return attempt

    def _resolve(self, attempt_id: str) -> ExecutionRecoveryAttempt:
        attempt = self._attempts_by_id.get(attempt_id)

        if attempt is None:
            raise ExecutionRecoveryAttemptError(f"No attempt is known under attempt ID {attempt_id!r}.")

        return attempt

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryAttemptError(f"Cannot use an empty or blank {field_name}.")
