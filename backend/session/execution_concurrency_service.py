from threading import (
    RLock,
)

from uuid import uuid4

from .execution_concurrency_limit import (
    ExecutionConcurrencyLimit,
)

from .execution_concurrency_error import (
    ExecutionConcurrencyError,
)


class ExecutionConcurrencyService:
    """
    Controls how many execution jobs may run simultaneously within a
    scope (for example, a workspace).

    Behavior:
    - register() sets (or updates) the maximum number of concurrently
      running jobs allowed for a scope; re-registering a scope
      updates its limit without disturbing jobs already running in it
    - acquire() admits a job into a scope's running set, but only if
      the scope has spare capacity; the same job can never hold
      capacity in a scope more than once at a time
    - release() atomically returns a job's capacity to the scope

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._limits_by_scope = {}
        self._running_by_scope = {}
        self._lock = RLock()

    def register(self, scope_id: str, max_running: int) -> ExecutionConcurrencyLimit:
        """
        Set or update the maximum number of concurrently running jobs
        allowed for a scope.

        Raises:
            ExecutionConcurrencyError: If scope_id is None or blank,
                or max_running is not an int of at least 1
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            existing = self._limits_by_scope.get(scope_id)
            limit_id = existing.limit_id if existing is not None else str(uuid4())

            limit = ExecutionConcurrencyLimit(
                limit_id=limit_id,
                scope_id=scope_id,
                max_running=max_running,
                enabled=True,
            )

            self._limits_by_scope[scope_id] = limit
            self._running_by_scope.setdefault(scope_id, set())

            return limit

    def can_start(self, scope_id: str) -> bool:
        """
        Whether the scope currently has spare capacity for another
        job to start.

        Raises:
            ExecutionConcurrencyError: If scope_id is None or blank,
                or no limit is registered for it
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            limit = self._resolve(scope_id)

            if not limit.enabled:
                return False

            return len(self._running_by_scope[scope_id]) < limit.max_running

    def acquire(self, scope_id: str, job_id: str) -> ExecutionConcurrencyLimit:
        """
        Admit a job into a scope's running set.

        Raises:
            ExecutionConcurrencyError: If scope_id or job_id is None
                or blank, no limit is registered for scope_id, job_id
                already holds capacity in scope_id, or the scope's
                capacity is exhausted
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_text(job_id, "job ID")

        with self._lock:
            limit = self._resolve(scope_id)
            running = self._running_by_scope[scope_id]

            if job_id in running:
                raise ExecutionConcurrencyError(
                    f"Cannot acquire capacity for job ID {job_id!r} in scope {scope_id!r}: it already holds capacity."
                )

            if not limit.enabled or len(running) >= limit.max_running:
                raise ExecutionConcurrencyError(
                    f"Cannot acquire capacity for job ID {job_id!r} in scope {scope_id!r}: capacity is exhausted."
                )

            running.add(job_id)

            return limit

    def release(self, scope_id: str, job_id: str) -> None:
        """
        Atomically return a job's capacity to its scope.

        Raises:
            ExecutionConcurrencyError: If scope_id or job_id is None
                or blank, no limit is registered for scope_id, or
                job_id does not currently hold capacity in scope_id
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_text(job_id, "job ID")

        with self._lock:
            self._resolve(scope_id)
            running = self._running_by_scope[scope_id]

            if job_id not in running:
                raise ExecutionConcurrencyError(
                    f"Cannot release capacity for job ID {job_id!r} in scope {scope_id!r}: it does not hold capacity."
                )

            running.discard(job_id)

    def running(self, scope_id: str) -> int:
        """
        The number of jobs currently holding capacity in a scope.

        Raises:
            ExecutionConcurrencyError: If scope_id is None or blank,
                or no limit is registered for it
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            self._resolve(scope_id)

            return len(self._running_by_scope[scope_id])

    def _resolve(self, scope_id: str) -> ExecutionConcurrencyLimit:
        limit = self._limits_by_scope.get(scope_id)

        if limit is None:
            raise ExecutionConcurrencyError(f"No concurrency limit is registered for scope ID {scope_id!r}.")

        return limit

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionConcurrencyError(f"Cannot use an empty or blank {field_name}.")
