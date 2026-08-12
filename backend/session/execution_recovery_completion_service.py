from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_recovery_result_error import (
    ExecutionRecoveryResultError,
)

from .execution_recovery_result import (
    ExecutionRecoveryResult,
)


class ExecutionRecoveryCompletionService:
    """
    Finalizes recovery only when every required recovery component
    succeeds, producing one auditable outcome per session.

    A session's validation gate, unresolved conflicts, and latest
    recovery attempt are assumed to already exist elsewhere; this
    service depends on plain resolver callables for them rather than
    a concrete store:
    - gate_resolver(session_id) -> the session's validation gate (an
      object with .status and .checkpoint_id), or None
    - unresolved_conflicts_resolver(session_id) -> the session's
      outstanding, unresolved conflicts; matches the signature of an
      execution recovery conflict service's conflicts() method
    - latest_attempt_resolver(session_id) -> the session's most
      recent recovery attempt (an object with .status and
      .attempt_number), or None

    Behavior:
    - complete() checks, in order, that the gate is OPEN, that no
      conflicts remain unresolved, and that the latest attempt
      SUCCEEDED; it records COMPLETED only if every check passes,
      otherwise FAILED with the first failing reason. A session
      whose recovery has already COMPLETED cannot complete again
    - status() looks up a session's recorded outcome
    - failed() looks up a session's failure reason, or None if it
      COMPLETED
    - reset() clears a FAILED result so complete() can be tried
      again; a COMPLETED result can never be reset

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, gate_resolver, unresolved_conflicts_resolver, latest_attempt_resolver):
        self._gate_resolver = gate_resolver
        self._unresolved_conflicts_resolver = unresolved_conflicts_resolver
        self._latest_attempt_resolver = latest_attempt_resolver
        self._results_by_session = {}
        self._lock = RLock()

    def complete(self, session_id: str) -> ExecutionRecoveryResult:
        """
        Check the session's gate, unresolved conflicts, and latest
        recovery attempt, and record the outcome.

        Raises:
            ExecutionRecoveryResultError: If session_id is None or
                blank, recovery for it has already COMPLETED, or no
                validation gate is known for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            existing = self._results_by_session.get(session_id)

            if existing is not None and existing.status == "COMPLETED":
                raise ExecutionRecoveryResultError(
                    f"Recovery for session ID {session_id!r} has already COMPLETED; it is terminal."
                )

            gate = self._gate_resolver(session_id)

            if gate is None:
                raise ExecutionRecoveryResultError(f"No validation gate is known for session ID {session_id!r}.")

            unresolved_conflicts = tuple(self._unresolved_conflicts_resolver(session_id) or ())
            latest_attempt = self._latest_attempt_resolver(session_id)

            attempts = latest_attempt.attempt_number if latest_attempt is not None else 0

            if gate.status != "OPEN":
                failure_reason = f"Validation gate is {gate.status}, not OPEN."
            elif unresolved_conflicts:
                failure_reason = f"{len(unresolved_conflicts)} unresolved conflict(s) remain."
            elif latest_attempt is None or latest_attempt.status != "SUCCEEDED":
                attempt_status = latest_attempt.status if latest_attempt is not None else "no attempt recorded"
                failure_reason = f"Recovery attempt did not succeed: {attempt_status}."
            else:
                failure_reason = None

            if failure_reason is None:
                result = ExecutionRecoveryResult(
                    session_id=session_id,
                    checkpoint_id=gate.checkpoint_id,
                    status="COMPLETED",
                    attempts=attempts,
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                result = ExecutionRecoveryResult(
                    session_id=session_id,
                    checkpoint_id=gate.checkpoint_id,
                    status="FAILED",
                    attempts=attempts,
                    failure_reason=failure_reason,
                )

            self._results_by_session[session_id] = result

            return result

    def status(self, session_id: str) -> str:
        """
        Look up a session's recorded outcome.

        Raises:
            ExecutionRecoveryResultError: If session_id is None or
                blank, or no result is recorded for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._resolve(session_id).status

    def failed(self, session_id: str) -> str | None:
        """
        Look up a session's failure reason, or None if it COMPLETED.

        Raises:
            ExecutionRecoveryResultError: If session_id is None or
                blank, or no result is recorded for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._resolve(session_id).failure_reason

    def reset(self, session_id: str) -> None:
        """
        Clear a FAILED result so complete() can be tried again.

        Raises:
            ExecutionRecoveryResultError: If session_id is None or
                blank, no result is recorded for it, or it COMPLETED
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            result = self._resolve(session_id)

            if result.status == "COMPLETED":
                raise ExecutionRecoveryResultError(
                    f"Recovery for session ID {session_id!r} has already COMPLETED; it is terminal and cannot "
                    "be reset."
                )

            del self._results_by_session[session_id]

    def _resolve(self, session_id: str) -> ExecutionRecoveryResult:
        result = self._results_by_session.get(session_id)

        if result is None:
            raise ExecutionRecoveryResultError(f"No recovery result is recorded for session ID {session_id!r}.")

        return result

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryResultError(f"Cannot use an empty or blank {field_name}.")
