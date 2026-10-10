from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_dead_letter_job import (
    ExecutionDeadLetterJob,
)

from .execution_dead_letter_error import (
    ExecutionDeadLetterError,
)

LIFECYCLE_ACTIVE = "ACTIVE"

LIFECYCLE_RETRIED = "RETRIED"

LIFECYCLE_DISCARDED = "DISCARDED"


class ExecutionDeadLetterService:
    """
    Safely isolates jobs that repeatedly fail scheduling instead of
    retrying them indefinitely.

    An optional on_retry callback (invoked with a job_id) is the
    service's hook into the surrounding queue/retry infrastructure;
    it is how a retried job is actually signalled to return to
    QUEUED. It defaults to a no-op so the service is fully testable
    on its own.

    Behavior:
    - move() counts a scheduling failure for job_id; a job is only
      actually moved to the dead-letter once its accumulated failures
      exceed retry_threshold. Calls that do not yet exceed the
      threshold return None
    - The ExecutionDeadLetterJob a successful move() produces is never
      mutated afterward; retry() and discard() both return that exact
      same record, so the original job metadata it carries is always
      preserved
    - retry() invokes on_retry(job_id) and resets the job's failure
      count, then puts the record in a terminal RETRIED state
    - discard() puts the record in a terminal DISCARDED state
    - Once a record is RETRIED or DISCARDED, retrying or discarding it
      again is rejected

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, retry_threshold: int = 3, on_retry=None):
        if not isinstance(retry_threshold, int) or isinstance(retry_threshold, bool) or retry_threshold < 1:
            raise ExecutionDeadLetterError(
                "Cannot initialize a dead-letter service with a retry_threshold that is not a positive int."
            )

        self._retry_threshold = retry_threshold
        self._on_retry = on_retry if on_retry is not None else (lambda job_id: None)
        self._failure_counts_by_job = {}
        self._records_by_id = {}
        self._lifecycle_by_id = {}
        self._lock = RLock()

    def move(self, job_id: str, reason: str):
        """
        Count a scheduling failure for job_id, moving it to the
        dead-letter once its accumulated failures exceed
        retry_threshold.

        Returns:
            The new ExecutionDeadLetterJob if this failure pushed
            job_id over retry_threshold, otherwise None

        Raises:
            ExecutionDeadLetterError: If job_id or reason is None or
                blank
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(reason, "reason")

        with self._lock:
            failure_count = self._failure_counts_by_job.get(job_id, 0) + 1
            self._failure_counts_by_job[job_id] = failure_count

            if failure_count <= self._retry_threshold:
                return None

            record = ExecutionDeadLetterJob(
                dead_letter_id=str(uuid4()),
                job_id=job_id,
                failure_count=failure_count,
                reason=reason,
                moved_at=datetime.now(timezone.utc),
            )

            self._records_by_id[record.dead_letter_id] = record
            self._lifecycle_by_id[record.dead_letter_id] = LIFECYCLE_ACTIVE

            return record

    def retry(self, dead_letter_id: str) -> ExecutionDeadLetterJob:
        """
        Send a dead-lettered job back to QUEUED.

        Raises:
            ExecutionDeadLetterError: If dead_letter_id is None or
                blank, no record is registered under it, or it is
                already RETRIED or DISCARDED
        """

        self._validate_text(dead_letter_id, "dead-letter ID")

        with self._lock:
            record = self._resolve(dead_letter_id)
            self._require_active(dead_letter_id)

            self._lifecycle_by_id[dead_letter_id] = LIFECYCLE_RETRIED
            self._failure_counts_by_job[record.job_id] = 0
            self._on_retry(record.job_id)

            return record

    def discard(self, dead_letter_id: str) -> ExecutionDeadLetterJob:
        """
        Terminally discard a dead-lettered job; it will never be
        retried.

        Raises:
            ExecutionDeadLetterError: If dead_letter_id is None or
                blank, no record is registered under it, or it is
                already RETRIED or DISCARDED
        """

        self._validate_text(dead_letter_id, "dead-letter ID")

        with self._lock:
            record = self._resolve(dead_letter_id)
            self._require_active(dead_letter_id)

            self._lifecycle_by_id[dead_letter_id] = LIFECYCLE_DISCARDED

            return record

    def list(self, job_id: str) -> tuple:
        """
        Every dead-letter record ever created for job_id, in the
        order they were moved.
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            return tuple(
                record for record in self._records_by_id.values() if record.job_id == job_id
            )

    def _require_active(self, dead_letter_id: str) -> None:
        if self._lifecycle_by_id[dead_letter_id] != LIFECYCLE_ACTIVE:
            raise ExecutionDeadLetterError(
                f"Cannot act on dead-letter ID {dead_letter_id!r}: it is already "
                f"{self._lifecycle_by_id[dead_letter_id]}."
            )

    def _resolve(self, dead_letter_id: str) -> ExecutionDeadLetterJob:
        record = self._records_by_id.get(dead_letter_id)

        if record is None:
            raise ExecutionDeadLetterError(f"No dead-letter record is registered under ID {dead_letter_id!r}.")

        return record

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionDeadLetterError(f"Cannot use an empty or blank {field_name}.")
