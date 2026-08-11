from threading import (
    RLock,
)

from .execution_observation_error_error import (
    ExecutionObservationErrorError,
)

from .execution_observation_error import (
    ExecutionObservationError,
)


class ExecutionObservationErrorService:
    """
    Maintains an append-only log of execution observation errors,
    kept queryable by session and stage for diagnosis.

    The service's responsibility is error bookkeeping only. It does
    not decide when a failure happens or what it means; a caller
    builds a fully-formed ExecutionObservationError and record()s it
    here. Execution sessions and stages themselves are assumed to
    already exist and are never read or mutated by this service.

    Behavior:
    - record() is append-only: a caller cannot edit or remove an
      error once recorded, and recording the same error ID twice is
      rejected as a duplicate
    - The original message given to record() is never altered
    - history(), stage_errors(), and latest() all return errors in
      chronological (timestamp) order, regardless of the order they
      were record()ed in
    - stage_errors() only matches errors recorded with that exact
      stage_id; an error recorded without one (stage_id is None) is
      never returned by it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._errors_by_id = {}
        self._error_ids_by_session = {}
        self._lock = RLock()

    def record(self, error: ExecutionObservationError) -> ExecutionObservationError:
        """
        Append a new observation error.

        Raises:
            ExecutionObservationErrorError: If error is not an
                ExecutionObservationError, or its error ID is already
                recorded
        """

        if not isinstance(error, ExecutionObservationError):
            raise ExecutionObservationErrorError(
                "Cannot record an invalid error: error must be an ExecutionObservationError."
            )

        with self._lock:
            if error.error_id in self._errors_by_id:
                raise ExecutionObservationErrorError(f"Error ID {error.error_id!r} is already recorded.")

            self._errors_by_id[error.error_id] = error
            self._error_ids_by_session.setdefault(error.session_id, []).append(error.error_id)

            return error

    def history(self, session_id: str) -> list:
        """
        List every recorded error for a session, oldest to newest.

        Raises:
            ExecutionObservationErrorError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            errors = [
                self._errors_by_id[error_id] for error_id in self._error_ids_by_session.get(session_id, [])
            ]

            return sorted(errors, key=lambda error: error.timestamp)

    def stage_errors(self, session_id: str, stage_id: str) -> list:
        """
        List a session's recorded errors associated with one stage,
        oldest to newest.

        Raises:
            ExecutionObservationErrorError: If session_id or
                stage_id is None or blank
        """

        self._validate_id(stage_id, "stage ID")

        return [error for error in self.history(session_id) if error.stage_id == stage_id]

    def latest(self, session_id: str) -> ExecutionObservationError:
        """
        Look up a session's most recent error.

        Raises:
            ExecutionObservationErrorError: If session_id is None or
                blank, or it has no recorded errors
        """

        history = self.history(session_id)

        if not history:
            raise ExecutionObservationErrorError(f"Session ID {session_id!r} has no recorded errors.")

        return history[-1]

    def count(self, session_id: str) -> int:
        """
        Count how many errors are recorded for a session.

        Raises:
            ExecutionObservationErrorError: If session_id is None or
                blank
        """

        return len(self.history(session_id))

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationErrorError(f"Cannot use an empty or blank {field_name}.")
