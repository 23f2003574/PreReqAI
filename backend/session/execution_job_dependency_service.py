from threading import (
    RLock,
)

from .execution_job_dependency import (
    ExecutionJobDependency,
    STATUS_SUCCEEDED,
)

from .execution_job_dependency_error import (
    ExecutionJobDependencyError,
)


class ExecutionJobDependencyService:
    """
    Tracks which execution jobs must reach a required status before a
    dependent job is allowed to run.

    Composes with an existing job status-tracking service (anything
    exposing `status(job_id)`, raising when a job is unknown), used
    as the source of truth for whether a job exists and its current
    status.

    Behavior:
    - add() registers that job_id may not run until depends_on
      reaches required_status; self-dependencies and dependencies on
      an unknown job are rejected, as is any addition that would
      create a dependency cycle
    - remove() drops a previously registered dependency
    - ready() reports whether every dependency registered for a job
      is currently satisfied; a job with no dependencies is always
      ready

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, status_service):
        self._status_service = status_service
        self._records_by_edge = {}
        self._depends_on_by_job = {}
        self._lock = RLock()

    def add(self, job_id: str, depends_on: str, required_status: str = STATUS_SUCCEEDED) -> ExecutionJobDependency:
        """
        Register that job_id may not run until depends_on reaches
        required_status.

        Raises:
            ExecutionJobDependencyError: If job_id or depends_on is
                None or blank, job_id equals depends_on, either job is
                unknown to the status service, or the dependency would
                create a cycle
        """

        if job_id == depends_on:
            raise ExecutionJobDependencyError(
                f"Cannot make job ID {job_id!r} depend on itself."
            )

        with self._lock:
            self._require_known_job(job_id)
            self._require_known_job(depends_on)

            if self._creates_cycle(job_id, depends_on):
                raise ExecutionJobDependencyError(
                    f"Cannot add dependency: job ID {job_id!r} depending on {depends_on!r} would create a cycle."
                )

            record = ExecutionJobDependency(
                job_id=job_id,
                depends_on=depends_on,
                required_status=required_status,
            )

            edge = (job_id, depends_on)

            if edge not in self._records_by_edge:
                self._depends_on_by_job.setdefault(job_id, []).append(depends_on)

            self._records_by_edge[edge] = record

            return record

    def remove(self, job_id: str, depends_on: str) -> None:
        """
        Drop a previously registered dependency.

        Raises:
            ExecutionJobDependencyError: If job_id or depends_on is
                None or blank, or no such dependency is registered
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(depends_on, "depends_on job ID")

        with self._lock:
            edge = (job_id, depends_on)

            if edge not in self._records_by_edge:
                raise ExecutionJobDependencyError(
                    f"No dependency is registered from job ID {job_id!r} on {depends_on!r}."
                )

            del self._records_by_edge[edge]
            self._depends_on_by_job[job_id].remove(depends_on)

    def dependencies(self, job_id: str) -> tuple:
        """
        Every dependency currently registered for job_id, in the
        order they were added.
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            return tuple(
                self._records_by_edge[(job_id, depends_on)]
                for depends_on in self._depends_on_by_job.get(job_id, [])
            )

    def ready(self, job_id: str) -> bool:
        """
        Whether every dependency registered for job_id is currently
        satisfied. A job with no dependencies is always ready.

        Raises:
            ExecutionJobDependencyError: If job_id is None or blank,
                or job_id is unknown to the status service
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            self._require_known_job(job_id)

            for depends_on in self._depends_on_by_job.get(job_id, []):
                record = self._records_by_edge[(job_id, depends_on)]

                try:
                    status = self._status_service.status(depends_on)
                except Exception:
                    return False

                if status != record.required_status:
                    return False

            return True

    def _creates_cycle(self, job_id: str, depends_on: str) -> bool:
        visited = set()
        stack = [depends_on]

        while stack:
            current = stack.pop()

            if current == job_id:
                return True

            if current in visited:
                continue

            visited.add(current)

            stack.extend(self._depends_on_by_job.get(current, []))

        return False

    def _require_known_job(self, job_id: str) -> None:
        try:
            self._status_service.status(job_id)
        except Exception as error:
            raise ExecutionJobDependencyError(
                f"No job is known under job ID {job_id!r}."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionJobDependencyError(f"Cannot use an empty or blank {field_name}.")
