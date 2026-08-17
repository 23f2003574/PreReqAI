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

from uuid import uuid4

from .execution_runtime_dispatch import (
    ExecutionRuntimeDispatch,
    STATUS_CANCELLED,
    STATUS_DISPATCHED,
)

from .execution_runtime_dispatch_error import (
    ExecutionRuntimeDispatchError,
)


class ExecutionRuntimeDispatchService:
    """
    Turns an approved scheduled job into an explicit runtime dispatch
    request.

    Composes with an existing scheduler service (anything exposing
    `decision(job_id)` that returns an object with `.allowed` and
    `.scheduler_id`, matching ExecutionSchedulerService), used to
    confirm a job is schedulable before it can be dispatched. The
    decision's scheduler_id also serves as the dispatch's runtime
    target, since it is the concrete destination the decision
    pipeline already resolved for the job.

    Behavior:
    - dispatch() admits a new DISPATCHED record, but only for a job
      whose latest scheduler decision is allowed, and only if the job
      does not already have an active dispatch
    - cancel() is idempotent: cancelling an already-cancelled dispatch
      simply returns it unchanged. Once cancelled, a dispatch stays
      cancelled; a cancelled dispatch can never start, and dispatch()
      always opens a new record rather than reviving one
    - active() reports the currently active (DISPATCHED) dispatches
      issued to a given target

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, scheduler_service):
        self._scheduler_service = scheduler_service
        self._dispatches_by_id = {}
        self._lock = RLock()

    def dispatch(self, job_id: str) -> ExecutionRuntimeDispatch:
        """
        Hand job_id off to its assigned scheduler as a runtime
        dispatch.

        Raises:
            ExecutionRuntimeDispatchError: If job_id is None or
                blank, job_id has no recorded schedule decision,
                job_id's latest decision is not allowed, or job_id
                already has an active dispatch
        """

        self._validate_text(job_id, "job ID")

        try:
            decision = self._scheduler_service.decision(job_id)
        except Exception as error:
            raise ExecutionRuntimeDispatchError(
                f"Cannot dispatch job ID {job_id!r}: it is unknown."
            ) from error

        if not decision.allowed:
            raise ExecutionRuntimeDispatchError(
                f"Cannot dispatch job ID {job_id!r}: it is not schedulable."
            )

        with self._lock:
            if self._active_for_job(job_id) is not None:
                raise ExecutionRuntimeDispatchError(
                    f"Cannot dispatch job ID {job_id!r}: it already has an active dispatch."
                )

            dispatch = ExecutionRuntimeDispatch(
                dispatch_id=str(uuid4()),
                job_id=job_id,
                scheduler_id=decision.scheduler_id,
                target=decision.scheduler_id,
                status=STATUS_DISPATCHED,
                dispatched_at=datetime.now(timezone.utc),
            )

            self._dispatches_by_id[dispatch.dispatch_id] = dispatch

            return dispatch

    def cancel(self, dispatch_id: str) -> ExecutionRuntimeDispatch:
        """
        Cancel a dispatch. Idempotent: cancelling an already-cancelled
        dispatch simply returns it unchanged.

        Raises:
            ExecutionRuntimeDispatchError: If dispatch_id is None or
                blank, or no dispatch is registered under it
        """

        self._validate_text(dispatch_id, "dispatch ID")

        with self._lock:
            dispatch = self._resolve(dispatch_id)

            if dispatch.status == STATUS_CANCELLED:
                return dispatch

            cancelled = replace(dispatch, status=STATUS_CANCELLED)
            self._dispatches_by_id[dispatch_id] = cancelled

            return cancelled

    def status(self, dispatch_id: str) -> str:
        """
        The current status of a dispatch.

        Raises:
            ExecutionRuntimeDispatchError: If dispatch_id is None or
                blank, or no dispatch is registered under it
        """

        self._validate_text(dispatch_id, "dispatch ID")

        with self._lock:
            return self._resolve(dispatch_id).status

    def active(self, scope_id: str) -> tuple:
        """
        The currently active (DISPATCHED) dispatches issued to
        scope_id (matched against each dispatch's target).
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return tuple(
                dispatch
                for dispatch in self._dispatches_by_id.values()
                if dispatch.target == scope_id and dispatch.status == STATUS_DISPATCHED
            )

    def _active_for_job(self, job_id: str):
        for dispatch in self._dispatches_by_id.values():
            if dispatch.job_id == job_id and dispatch.status == STATUS_DISPATCHED:
                return dispatch

        return None

    def _resolve(self, dispatch_id: str) -> ExecutionRuntimeDispatch:
        dispatch = self._dispatches_by_id.get(dispatch_id)

        if dispatch is None:
            raise ExecutionRuntimeDispatchError(
                f"No dispatch is recorded under dispatch ID {dispatch_id!r}."
            )

        return dispatch

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeDispatchError(f"Cannot use an empty or blank {field_name}.")
