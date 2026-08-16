from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_job import (
    ExecutionJob,
    STATUS_CANCELLED,
    STATUS_QUEUED,
    STATUS_READY,
)

from .execution_job_error import (
    ExecutionJobError,
)


class ExecutionJobQueueService:
    """
    Durable FIFO queue of execution jobs waiting to be scheduled.

    Behavior:
    - enqueue() admits a new, QUEUED job in FIFO order; the same
      job_id can never be enqueued more than once
    - dequeue() atomically removes the job at the front of the FIFO
      order and transitions it to READY; only a QUEUED job can be
      dequeued
    - peek() reports the job at the front of the FIFO order without
      mutating it or the queue
    - cancel() transitions a QUEUED job to CANCELLED, removing it from
      FIFO order; a cancelled job can never be dequeued

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._jobs_by_id = {}
        self._queued_ids = []
        self._lock = RLock()

    def enqueue(self, job: ExecutionJob) -> ExecutionJob:
        """
        Admit a new job at the back of the FIFO queue.

        Raises:
            ExecutionJobError: If job is None, job.status is not
                QUEUED, or a job is already registered under
                job.job_id
        """

        if job is None:
            raise ExecutionJobError("Cannot enqueue a None job.")

        if job.status != STATUS_QUEUED:
            raise ExecutionJobError(
                f"Cannot enqueue job ID {job.job_id!r}: it must be QUEUED, not {job.status!r}."
            )

        with self._lock:
            if job.job_id in self._jobs_by_id:
                raise ExecutionJobError(
                    f"Cannot enqueue job ID {job.job_id!r}: a job is already registered under it."
                )

            self._jobs_by_id[job.job_id] = job
            self._queued_ids.append(job.job_id)

            return job

    def dequeue(self):
        """
        Remove and start the job at the front of the FIFO queue.

        Returns:
            The job, now READY, or None if the queue is empty
        """

        with self._lock:
            if not self._queued_ids:
                return None

            job_id = self._queued_ids.pop(0)
            job = self._jobs_by_id[job_id]

            ready = replace(job, status=STATUS_READY)
            self._jobs_by_id[job_id] = ready

            return ready

    def peek(self):
        """
        Look at the job at the front of the FIFO queue without
        dequeueing it.

        Returns:
            The job that dequeue() would return next, or None if the
            queue is empty
        """

        with self._lock:
            if not self._queued_ids:
                return None

            return self._jobs_by_id[self._queued_ids[0]]

    def cancel(self, job_id: str) -> ExecutionJob:
        """
        Cancel a queued job so it is removed from FIFO order and can
        never be dequeued.

        Raises:
            ExecutionJobError: If job_id is None or blank, no job is
                registered under it, or the job is not QUEUED
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            job = self._resolve(job_id)

            if job.status != STATUS_QUEUED:
                raise ExecutionJobError(
                    f"Cannot cancel job ID {job_id!r}: it is not QUEUED (status is {job.status!r})."
                )

            cancelled = replace(job, status=STATUS_CANCELLED)
            self._jobs_by_id[job_id] = cancelled
            self._queued_ids.remove(job_id)

            return cancelled

    def status(self, job_id: str) -> str:
        """
        The current status of a registered job.

        Raises:
            ExecutionJobError: If job_id is None or blank, or no job
                is registered under it
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            return self._resolve(job_id).status

    def size(self) -> int:
        """
        The number of jobs currently QUEUED, awaiting dequeue.
        """

        with self._lock:
            return len(self._queued_ids)

    def _resolve(self, job_id: str) -> ExecutionJob:
        job = self._jobs_by_id.get(job_id)

        if job is None:
            raise ExecutionJobError(f"No job is recorded under job ID {job_id!r}.")

        return job

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionJobError(f"Cannot use an empty or blank {field_name}.")
