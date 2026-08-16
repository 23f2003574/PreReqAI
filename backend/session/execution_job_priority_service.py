from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_job import (
    STATUS_QUEUED,
)

from .execution_job_priority import (
    ExecutionJobPriority,
    PRIORITIES,
    PRIORITY_RANK,
)

from .execution_job_priority_error import (
    ExecutionJobPriorityError,
)


class ExecutionJobPriorityService:
    """
    Tracks the scheduling priority of execution jobs so urgent jobs
    can overtake normal work without breaking FIFO order within the
    same priority.

    Composes with an existing execution job queue service, used as
    the source of truth for whether a job exists and whether it is
    still QUEUED.

    Behavior:
    - set() assigns or updates a job's priority; every update refreshes
      updated_at, which also determines the job's FIFO position among
      jobs sharing its new priority
    - ordered() and highest() only consider jobs that are still QUEUED
      in the job queue; a cancelled (or otherwise no longer queued)
      job is excluded even if a priority was previously set for it
    - ordered() ranks jobs highest priority first; jobs sharing a
      priority are returned oldest-updated_at first

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, queue_service):
        self._queue_service = queue_service
        self._priorities_by_job_id = {}
        self._lock = RLock()

    def set(self, job_id: str, priority: str) -> ExecutionJobPriority:
        """
        Assign or update a job's priority.

        Raises:
            ExecutionJobPriorityError: If job_id is None or blank,
                priority is not one of PRIORITIES, or no job is known
                to the job queue under job_id
        """

        self._validate_text(job_id, "job ID")

        if priority not in PRIORITIES:
            raise ExecutionJobPriorityError(
                f"Cannot set priority for job ID {job_id!r}: unknown priority {priority!r}."
            )

        with self._lock:
            self._require_known_job(job_id)

            record = ExecutionJobPriority(
                job_id=job_id,
                priority=priority,
                updated_at=datetime.now(timezone.utc),
            )

            self._priorities_by_job_id[job_id] = record

            return record

    def get(self, job_id: str) -> ExecutionJobPriority:
        """
        The current priority record for a job.

        Raises:
            ExecutionJobPriorityError: If job_id is None or blank, or
                no priority has been set for job_id
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            return self._resolve(job_id)

    def ordered(self) -> tuple:
        """
        Every still-QUEUED job with a priority assigned, ranked
        highest priority first and, within a priority, oldest
        updated_at first.
        """

        with self._lock:
            active = [record for record in self._priorities_by_job_id.values() if self._is_queued(record.job_id)]

            active.sort(key=lambda record: (-PRIORITY_RANK[record.priority], record.updated_at))

            return tuple(active)

    def highest(self):
        """
        The single job that should be scheduled next, by priority
        then FIFO.

        Returns:
            The highest-ranked ExecutionJobPriority, or None if no
            QUEUED job has a priority assigned
        """

        ordered = self.ordered()

        return ordered[0] if ordered else None

    def _is_queued(self, job_id: str) -> bool:
        try:
            status = self._queue_service.status(job_id)
        except Exception:
            return False

        return status == STATUS_QUEUED

    def _require_known_job(self, job_id: str) -> None:
        try:
            self._queue_service.status(job_id)
        except Exception as error:
            raise ExecutionJobPriorityError(
                f"Cannot set priority for job ID {job_id!r}: it is unknown to the job queue."
            ) from error

    def _resolve(self, job_id: str) -> ExecutionJobPriority:
        record = self._priorities_by_job_id.get(job_id)

        if record is None:
            raise ExecutionJobPriorityError(f"No priority is recorded under job ID {job_id!r}.")

        return record

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionJobPriorityError(f"Cannot use an empty or blank {field_name}.")
