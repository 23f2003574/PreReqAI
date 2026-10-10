from threading import (
    RLock,
)

from .execution_recovery_state_error import (
    ExecutionRecoveryStateError,
)

from .execution_recovery_state import (
    ExecutionRecoveryState,
)


class ExecutionRecoveryStateService:
    """
    Reconstructs runtime state from a validated recovery checkpoint,
    and applies it to resume an interrupted execution session.

    Checkpoints, their validation outcome, and session statuses are
    assumed to already exist elsewhere; this service depends on
    plain resolver callables for them rather than a concrete store:
    - checkpoint_resolver(checkpoint_id) -> checkpoint or None
    - checkpoint_validation_resolver(checkpoint_id) -> True if the
      checkpoint has passed validation, False or None otherwise
    - session_status_resolver(session_id) -> status string or None

    Behavior:
    - reconstruct() rebuilds state from a checkpoint, but only if
      the checkpoint has passed validation; the result becomes that
      session's pending reconstructed state, replacing any earlier
      one
    - state() looks up a session's pending reconstructed state, or
      None if there isn't one
    - apply() hands back the pending reconstructed state to resume
      the session, but refuses to do so while the session is
      ACTIVE, so it can never overwrite execution already in
      progress; on success, the pending state is cleared
    - clear() discards a session's pending reconstructed state,
      whether or not one exists

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, checkpoint_resolver, checkpoint_validation_resolver, session_status_resolver):
        self._checkpoint_resolver = checkpoint_resolver
        self._checkpoint_validation_resolver = checkpoint_validation_resolver
        self._session_status_resolver = session_status_resolver
        self._state_by_session = {}
        self._lock = RLock()

    def reconstruct(self, checkpoint_id: str) -> ExecutionRecoveryState:
        """
        Rebuild runtime state from a checkpoint, provided it has
        passed validation. The result becomes the checkpoint's
        session's pending reconstructed state, replacing any earlier
        one.

        Raises:
            ExecutionRecoveryStateError: If checkpoint_id is None or
                blank, no checkpoint is known under it, or it has
                not passed validation
        """

        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._checkpoint_resolver(checkpoint_id)

            if checkpoint is None:
                raise ExecutionRecoveryStateError(f"No checkpoint is known under checkpoint ID {checkpoint_id!r}.")

            if not self._checkpoint_validation_resolver(checkpoint_id):
                raise ExecutionRecoveryStateError(
                    f"Cannot reconstruct state from checkpoint ID {checkpoint_id!r}: it has not passed validation."
                )

            state = ExecutionRecoveryState(
                session_id=checkpoint.session_id,
                checkpoint_id=checkpoint_id,
                stage_id=checkpoint.stage_id,
                variables=checkpoint.state,
            )

            self._state_by_session[checkpoint.session_id] = state

            return state

    def state(self, session_id: str) -> ExecutionRecoveryState | None:
        """
        Look up a session's pending reconstructed state.

        Raises:
            ExecutionRecoveryStateError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._state_by_session.get(session_id)

    def apply(self, session_id: str) -> ExecutionRecoveryState:
        """
        Hand back a session's pending reconstructed state to resume
        it, refusing to do so while the session is ACTIVE. Clears
        the pending state on success.

        Raises:
            ExecutionRecoveryStateError: If session_id is None or
                blank, no reconstructed state is pending for it, or
                the session is ACTIVE
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            pending = self._state_by_session.get(session_id)

            if pending is None:
                raise ExecutionRecoveryStateError(f"No reconstructed state is pending for session ID {session_id!r}.")

            status = self._session_status_resolver(session_id)

            if status == "ACTIVE":
                raise ExecutionRecoveryStateError(
                    f"Cannot apply reconstructed state to session ID {session_id!r}: it is ACTIVE, and applying "
                    "would overwrite active execution."
                )

            del self._state_by_session[session_id]

            return pending

    def clear(self, session_id: str) -> None:
        """
        Discard a session's pending reconstructed state, whether or
        not one exists.

        Raises:
            ExecutionRecoveryStateError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._state_by_session.pop(session_id, None)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryStateError(f"Cannot use an empty or blank {field_name}.")
