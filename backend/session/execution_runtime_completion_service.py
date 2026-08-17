from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_health import (
    STATUS_DEGRADED,
    STATUS_HEALTHY,
)

from .execution_runtime_completion import (
    ExecutionRuntimeCompletion,
    FINAL_STATUS_FAILED,
    FINAL_STATUS_SUCCEEDED,
)

from .execution_runtime_completion_error import (
    ExecutionRuntimeCompletionError,
)


class ExecutionRuntimeCompletionService:
    """
    Produces the final runtime outcome after lifecycle, health,
    resources, and shutdown have completed.

    Reuses the existing runtime lifecycle components directly rather
    than duck-typing a narrower interface:
        finalization_service: result(runtime_id); history(session_id)
            (ExecutionRuntimeFinalizationService)
        resource_service: active(runtime_id) -> tuple
            (ExecutionRuntimeResourceService)
        health_service: check(runtime_id) -> object with .status
            (ExecutionRuntimeHealthService)

    Behavior:
    - complete() produces a new, immutable completion, but only for a
      runtime that has already been finalized, holds no active
      resources, and whose health is resolved (HEALTHY or FAILED, not
      DEGRADED); a runtime can only be completed once, a second
      complete() for the same runtime is rejected outright
    - The completion's final_status is SUCCEEDED when health is
      HEALTHY, and FAILED when health is FAILED
    - status() and result() both report a runtime's completion
    - history() reports every completion for a session, reusing the
      finalization service's own session history to determine session
      membership

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, finalization_service, resource_service, health_service):
        self._finalization_service = finalization_service
        self._resource_service = resource_service
        self._health_service = health_service
        self._completions_by_runtime = {}
        self._lock = RLock()

    def complete(self, runtime_id: str) -> ExecutionRuntimeCompletion:
        """
        Produce runtime_id's final completion.

        Raises:
            ExecutionRuntimeCompletionError: If runtime_id is None or
                blank, it has already been completed, it has not been
                finalized, it still holds active resources, or its
                health is not resolved (DEGRADED)
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            if runtime_id in self._completions_by_runtime:
                raise ExecutionRuntimeCompletionError(
                    f"Cannot complete runtime ID {runtime_id!r}: it has already been completed."
                )

            try:
                finalized = self._finalization_service.result(runtime_id)
            except Exception as error:
                raise ExecutionRuntimeCompletionError(
                    f"Cannot complete runtime ID {runtime_id!r}: it has not been finalized."
                ) from error

            if self._resource_service.active(runtime_id):
                raise ExecutionRuntimeCompletionError(
                    f"Cannot complete runtime ID {runtime_id!r}: it still holds active resources."
                )

            health = self._health_service.check(runtime_id)

            if health.status == STATUS_DEGRADED:
                raise ExecutionRuntimeCompletionError(
                    f"Cannot complete runtime ID {runtime_id!r}: its health is not resolved "
                    f"(status is {health.status!r})."
                )

            final_status = FINAL_STATUS_SUCCEEDED if health.status == STATUS_HEALTHY else FINAL_STATUS_FAILED

            completion = ExecutionRuntimeCompletion(
                completion_id=str(uuid4()),
                runtime_id=runtime_id,
                final_status=final_status,
                health_status=health.status,
                output_ref=finalized.output_ref,
                completed_at=datetime.now(timezone.utc),
            )

            self._completions_by_runtime[runtime_id] = completion

            return completion

    def status(self, runtime_id: str) -> str:
        """
        The final_status of runtime_id's completion.

        Raises:
            ExecutionRuntimeCompletionError: If runtime_id is None or
                blank, or it has not been completed
        """

        return self.result(runtime_id).final_status

    def result(self, runtime_id: str) -> ExecutionRuntimeCompletion:
        """
        The completion produced for runtime_id.

        Raises:
            ExecutionRuntimeCompletionError: If runtime_id is None or
                blank, or it has not been completed
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            completion = self._completions_by_runtime.get(runtime_id)

            if completion is None:
                raise ExecutionRuntimeCompletionError(
                    f"No completion is recorded for runtime ID {runtime_id!r}."
                )

            return completion

    def history(self, session_id: str) -> tuple:
        """
        Every completion produced for a runtime finalized under
        session_id, in the order the finalization service recorded
        them.

        Raises:
            ExecutionRuntimeCompletionError: If session_id is None or
                blank, or no runtime finalized under it has been
                completed
        """

        self._validate_text(session_id, "session ID")

        try:
            finalized_results = self._finalization_service.history(session_id)
        except Exception as error:
            raise ExecutionRuntimeCompletionError(
                f"No completion is recorded for session ID {session_id!r}."
            ) from error

        with self._lock:
            completions = tuple(
                self._completions_by_runtime[result.runtime_id]
                for result in finalized_results
                if result.runtime_id in self._completions_by_runtime
            )

        if not completions:
            raise ExecutionRuntimeCompletionError(
                f"No completion is recorded for session ID {session_id!r}."
            )

        return completions

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeCompletionError(f"Cannot use an empty or blank {field_name}.")
