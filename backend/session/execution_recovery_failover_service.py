from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_recovery_failover_error import (
    ExecutionRecoveryFailoverError,
)

from .execution_recovery_failover import (
    ExecutionRecoveryFailover,
)


class ExecutionRecoveryFailoverService:
    """
    Automatically switches to a backup recovery checkpoint when a
    session's primary checkpoint cannot be restored.

    A checkpoint's validity is assumed to already exist elsewhere;
    this service depends on a plain resolver callable for it rather
    than a concrete store:
    - checkpoint_validation_resolver(checkpoint_id) -> True if the
      checkpoint has passed validation, False or None otherwise

    Behavior:
    - register() records a session's primary checkpoint and its
      backups, in priority order, as PENDING
    - execute() walks the primary, then each backup in order,
      validating each and selecting the first valid one; if it finds
      none, the failover becomes EXHAUSTED. Once RESOLVED or
      EXHAUSTED, re-running execute() changes nothing: the outcome
      is preserved
    - select() looks up the currently selected checkpoint ID, or
      None
    - status() looks up the current status

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, checkpoint_validation_resolver):
        self._checkpoint_validation_resolver = checkpoint_validation_resolver
        self._failovers_by_session = {}
        self._lock = RLock()

    def register(self, session_id: str, checkpoints) -> ExecutionRecoveryFailover:
        """
        Record a session's primary checkpoint and its backups, in
        priority order, as PENDING. Replaces any earlier failover
        recorded for the session.

        Raises:
            ExecutionRecoveryFailoverError: If session_id is None or
                blank, or checkpoints is empty
        """

        self._validate_id(session_id, "session ID")

        checkpoint_list = list(checkpoints) if checkpoints is not None else []

        if not checkpoint_list:
            raise ExecutionRecoveryFailoverError(
                f"Cannot register a failover for session ID {session_id!r} with no checkpoints."
            )

        primary_checkpoint_id, *backup_checkpoint_ids = checkpoint_list

        with self._lock:
            failover = ExecutionRecoveryFailover(
                session_id=session_id,
                primary_checkpoint_id=primary_checkpoint_id,
                backup_checkpoint_ids=tuple(backup_checkpoint_ids),
            )

            self._failovers_by_session[session_id] = failover

            return failover

    def execute(self, session_id: str) -> ExecutionRecoveryFailover:
        """
        Walk a session's primary checkpoint, then each backup in
        priority order, selecting the first one that passes
        validation. Leaves an already RESOLVED or EXHAUSTED failover
        unchanged.

        Raises:
            ExecutionRecoveryFailoverError: If session_id is None or
                blank, or no failover is registered for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            failover = self._resolve(session_id)

            if failover.status != "PENDING":
                return failover

            candidates = (failover.primary_checkpoint_id, *failover.backup_checkpoint_ids)

            selected_checkpoint = next(
                (candidate for candidate in candidates if self._checkpoint_validation_resolver(candidate)),
                None,
            )

            if selected_checkpoint is not None:
                updated = replace(failover, status="RESOLVED", selected_checkpoint=selected_checkpoint)
            else:
                updated = replace(failover, status="EXHAUSTED")

            self._failovers_by_session[session_id] = updated

            return updated

    def select(self, session_id: str) -> str | None:
        """
        Look up the checkpoint ID currently selected for a session.

        Raises:
            ExecutionRecoveryFailoverError: If session_id is None or
                blank, or no failover is registered for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._resolve(session_id).selected_checkpoint

    def status(self, session_id: str) -> str:
        """
        Look up the current status of a session's failover.

        Raises:
            ExecutionRecoveryFailoverError: If session_id is None or
                blank, or no failover is registered for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._resolve(session_id).status

    def _resolve(self, session_id: str) -> ExecutionRecoveryFailover:
        failover = self._failovers_by_session.get(session_id)

        if failover is None:
            raise ExecutionRecoveryFailoverError(f"No failover is registered for session ID {session_id!r}.")

        return failover

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryFailoverError(f"Cannot use an empty or blank {field_name}.")
