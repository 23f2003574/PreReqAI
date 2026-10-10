from threading import (
    RLock,
)

from .execution_recovery_rollback_error import (
    ExecutionRecoveryRollbackError,
)

from .execution_recovery_rollback import (
    ExecutionRecoveryRollback,
)


class ExecutionRecoveryRollbackService:
    """
    Safely undoes a partially applied recovery when resume fails
    after state has already been reconstructed.

    A session's recovery status, its current runtime state, and the
    checkpoint its active recovery attempt is using are assumed to
    already exist elsewhere; this service depends on plain resolver
    callables for them rather than a concrete store:
    - recovery_status_resolver(session_id) -> "ACTIVE" while a
      recovery attempt is in flight, "COMPLETED" once it has
      finished successfully, or None if the session is unknown
    - current_state_resolver(session_id) -> mapping of the session's
      current runtime variables
    - active_checkpoint_resolver(session_id) -> the checkpoint ID
      the session's active recovery attempt is using, or None

    Behavior:
    - prepare() captures a snapshot of a session's pre-recovery
      state, but only while its recovery is ACTIVE; a COMPLETED
      recovery can never be rolled back
    - execute() atomically commits the rollback: it re-checks that
      the recovery is still ACTIVE and that the rollback has not
      already been executed before making any change, so a failed
      execute() never leaves a rollback partially transitioned
    - status() looks up a rollback's current status, PREPARED or
      EXECUTED
    - restore() returns the preserved pre-recovery state, but only
      once the rollback has been EXECUTED

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, recovery_status_resolver, current_state_resolver, active_checkpoint_resolver):
        self._recovery_status_resolver = recovery_status_resolver
        self._current_state_resolver = current_state_resolver
        self._active_checkpoint_resolver = active_checkpoint_resolver
        self._rollbacks_by_id = {}
        self._status_by_id = {}
        self._lock = RLock()

    def prepare(self, session_id: str) -> ExecutionRecoveryRollback:
        """
        Capture a snapshot of a session's pre-recovery state, only
        while its recovery is ACTIVE.

        Raises:
            ExecutionRecoveryRollbackError: If session_id is None or
                blank, its recovery status is unknown or not ACTIVE,
                or it has no active checkpoint
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            status = self._recovery_status_resolver(session_id)

            if status is None:
                raise ExecutionRecoveryRollbackError(f"No recovery is known for session ID {session_id!r}.")

            if status != "ACTIVE":
                raise ExecutionRecoveryRollbackError(
                    f"Cannot prepare a rollback for session ID {session_id!r}: its recovery is {status}, not "
                    "ACTIVE."
                )

            checkpoint_id = self._active_checkpoint_resolver(session_id)

            if checkpoint_id is None:
                raise ExecutionRecoveryRollbackError(f"Session ID {session_id!r} has no active checkpoint.")

            current_state = self._current_state_resolver(session_id) or {}

            rollback = ExecutionRecoveryRollback(
                session_id=session_id,
                checkpoint_id=checkpoint_id,
                state=current_state,
            )

            self._rollbacks_by_id[rollback.rollback_id] = rollback
            self._status_by_id[rollback.rollback_id] = "PREPARED"

            return rollback

    def execute(self, rollback_id: str) -> ExecutionRecoveryRollback:
        """
        Atomically commit the rollback: re-checks that it is still
        PREPARED and that its session's recovery is still ACTIVE
        before making any change, so a failure never leaves it
        partially transitioned.

        Raises:
            ExecutionRecoveryRollbackError: If rollback_id is None
                or blank, no rollback is known under it, it is not
                PREPARED, or its session's recovery is no longer
                ACTIVE
        """

        self._validate_id(rollback_id, "rollback ID")

        with self._lock:
            rollback = self._resolve(rollback_id)
            current_status = self._status_by_id[rollback_id]

            if current_status != "PREPARED":
                raise ExecutionRecoveryRollbackError(
                    f"Cannot execute rollback ID {rollback_id!r}: it is {current_status}, not PREPARED."
                )

            recovery_status = self._recovery_status_resolver(rollback.session_id)

            if recovery_status != "ACTIVE":
                raise ExecutionRecoveryRollbackError(
                    f"Cannot execute rollback ID {rollback_id!r}: session ID {rollback.session_id!r}'s recovery "
                    f"is {recovery_status}, not ACTIVE."
                )

            self._status_by_id[rollback_id] = "EXECUTED"

            return rollback

    def status(self, rollback_id: str) -> str:
        """
        Look up a rollback's current status.

        Raises:
            ExecutionRecoveryRollbackError: If rollback_id is None
                or blank, or no rollback is known under it
        """

        self._validate_id(rollback_id, "rollback ID")

        with self._lock:
            self._resolve(rollback_id)

            return self._status_by_id[rollback_id]

    def restore(self, rollback_id: str):
        """
        Return the preserved pre-recovery state, but only once the
        rollback has been EXECUTED.

        Raises:
            ExecutionRecoveryRollbackError: If rollback_id is None
                or blank, no rollback is known under it, or it has
                not been executed
        """

        self._validate_id(rollback_id, "rollback ID")

        with self._lock:
            rollback = self._resolve(rollback_id)

            if self._status_by_id[rollback_id] != "EXECUTED":
                raise ExecutionRecoveryRollbackError(
                    f"Cannot restore rollback ID {rollback_id!r}: it has not been executed."
                )

            return rollback.state

    def _resolve(self, rollback_id: str) -> ExecutionRecoveryRollback:
        rollback = self._rollbacks_by_id.get(rollback_id)

        if rollback is None:
            raise ExecutionRecoveryRollbackError(f"No rollback is known under rollback ID {rollback_id!r}.")

        return rollback

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryRollbackError(f"Cannot use an empty or blank {field_name}.")
