from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_result import (
    ExecutionRuntimeResult,
    STATUS_COMPLETED,
)

from .execution_runtime_finalization_error import (
    ExecutionRuntimeFinalizationError,
)

STATE_STOPPED = "STOPPED"


class ExecutionRuntimeFinalizationService:
    """
    Finalizes a runtime after successful shutdown and produces its
    immutable execution outcome.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state and
    .session_id` and `history(runtime_id) -> ordered records with
    .updated_at`, matching ExecutionRuntimeStateService enriched with
    the session it belongs to), used as the single source of truth
    for whether a runtime is eligible to finalize, and to source the
    timestamps of its first and last recorded transitions.

    Behavior:
    - finalize() produces a new, immutable result, but only for a
      runtime whose current state is STOPPED, and only once per
      runtime; a second finalize() for the same runtime is rejected
      outright rather than returning the existing result
    - result() reports a runtime's finalized result
    - history() reports every result finalized for a session, in the
      order they were finalized

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._results_by_runtime = {}
        self._results_by_session = {}
        self._lock = RLock()

    def finalize(self, runtime_id: str) -> ExecutionRuntimeResult:
        """
        Finalize runtime_id, capturing its output reference and
        lifecycle timestamps into an immutable result.

        Raises:
            ExecutionRuntimeFinalizationError: If runtime_id is None
                or blank, runtime_id is unknown, its current state is
                not STOPPED, or it has already been finalized
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            if runtime_id in self._results_by_runtime:
                raise ExecutionRuntimeFinalizationError(
                    f"Cannot finalize runtime ID {runtime_id!r}: it has already been finalized."
                )

            try:
                current = self._state_service.state(runtime_id)
            except Exception as error:
                raise ExecutionRuntimeFinalizationError(
                    f"Cannot finalize runtime ID {runtime_id!r}: it is unknown."
                ) from error

            if current.state != STATE_STOPPED:
                raise ExecutionRuntimeFinalizationError(
                    f"Cannot finalize runtime ID {runtime_id!r}: it is not stopped "
                    f"(state is {current.state!r})."
                )

            history = self._state_service.history(runtime_id)

            if not history:
                raise ExecutionRuntimeFinalizationError(
                    f"Cannot finalize runtime ID {runtime_id!r}: it has no recorded lifecycle history."
                )

            result = ExecutionRuntimeResult(
                result_id=str(uuid4()),
                runtime_id=runtime_id,
                status=STATUS_COMPLETED,
                output_ref=f"runtime-output/{runtime_id}",
                started_at=history[0].updated_at,
                finished_at=history[-1].updated_at,
            )

            self._results_by_runtime[runtime_id] = result
            self._results_by_session.setdefault(current.session_id, []).append(result)

            return result

    def result(self, runtime_id: str) -> ExecutionRuntimeResult:
        """
        The finalized result for runtime_id.

        Raises:
            ExecutionRuntimeFinalizationError: If runtime_id is None
                or blank, or it has not been finalized
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            result = self._results_by_runtime.get(runtime_id)

            if result is None:
                raise ExecutionRuntimeFinalizationError(
                    f"No result is recorded for runtime ID {runtime_id!r}."
                )

            return result

    def history(self, session_id: str) -> tuple:
        """
        Every result finalized for session_id, in the order they were
        finalized.

        Raises:
            ExecutionRuntimeFinalizationError: If session_id is None
                or blank, or no result has been finalized for it
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            results = self._results_by_session.get(session_id)

            if not results:
                raise ExecutionRuntimeFinalizationError(
                    f"No result is recorded for session ID {session_id!r}."
                )

            return tuple(results)

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeFinalizationError(f"Cannot use an empty or blank {field_name}.")
