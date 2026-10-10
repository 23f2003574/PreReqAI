from threading import (
    RLock,
)

from .execution_recovery_conflict_error import (
    ExecutionRecoveryConflictError,
)

from .execution_recovery_conflict import (
    ExecutionRecoveryConflict,
)


class ExecutionRecoveryConflictService:
    """
    Detects fields where a recovery checkpoint's captured state
    differs from a session's current runtime state, and requires
    each one to be explicitly resolved before recovery can proceed.

    Checkpoints and current runtime state are assumed to already
    exist elsewhere; this service depends on plain resolver
    callables for them rather than a concrete store:
    - checkpoint_resolver(checkpoint_id) -> checkpoint or None
    - current_state_resolver(session_id) -> mapping of the session's
      current runtime variables

    Behavior:
    - detect() compares a checkpoint's captured state, field by
      field, against a session's current state, reporting one
      conflict per differing field; this replaces whatever was
      previously tracked for the session
    - conflicts() lists a session's outstanding, unresolved
      conflicts
    - resolve() records an explicit resolution for one conflict; it
      never applies that resolution to runtime state itself, only
      marks the conflict resolved
    - clear() discards a session's tracked conflicts, but refuses to
      do so while any remain unresolved, so an unresolved conflict
      blocks recovery from completing

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, checkpoint_resolver, current_state_resolver):
        self._checkpoint_resolver = checkpoint_resolver
        self._current_state_resolver = current_state_resolver
        self._conflicts_by_session = {}
        self._resolved_ids_by_session = {}
        self._session_by_conflict = {}
        self._lock = RLock()

    def detect(self, session_id: str, checkpoint_id: str) -> tuple:
        """
        Compare a checkpoint's captured state against a session's
        current state, field by field, reporting one conflict per
        differing field. Replaces whatever was previously tracked
        for the session.

        Raises:
            ExecutionRecoveryConflictError: If session_id or
                checkpoint_id is None or blank, no checkpoint is
                known under checkpoint_id, or it does not belong to
                session_id
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._checkpoint_resolver(checkpoint_id)

            if checkpoint is None:
                raise ExecutionRecoveryConflictError(f"No checkpoint is known under checkpoint ID {checkpoint_id!r}.")

            if checkpoint.session_id != session_id:
                raise ExecutionRecoveryConflictError(
                    f"Checkpoint ID {checkpoint_id!r} does not belong to session ID {session_id!r}."
                )

            current_state = self._current_state_resolver(session_id) or {}

            detected = tuple(
                ExecutionRecoveryConflict(
                    session_id=session_id,
                    checkpoint_id=checkpoint_id,
                    field=field_name,
                    checkpoint_value=checkpoint.state[field_name],
                    current_value=current_state.get(field_name),
                )
                for field_name in sorted(checkpoint.state)
                if checkpoint.state[field_name] != current_state.get(field_name)
            )

            self._discard(session_id)

            self._conflicts_by_session[session_id] = {conflict.conflict_id: conflict for conflict in detected}

            for conflict in detected:
                self._session_by_conflict[conflict.conflict_id] = session_id

            return detected

    def conflicts(self, session_id: str) -> tuple:
        """
        List a session's outstanding, unresolved conflicts.

        Raises:
            ExecutionRecoveryConflictError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            resolved_ids = self._resolved_ids_by_session.get(session_id, set())

            return tuple(
                conflict
                for conflict_id, conflict in self._conflicts_by_session.get(session_id, {}).items()
                if conflict_id not in resolved_ids
            )

    def resolve(self, conflict_id: str, resolution) -> ExecutionRecoveryConflict:
        """
        Record an explicit resolution for one conflict. Never
        applies the resolution to runtime state itself; only marks
        the conflict resolved.

        Raises:
            ExecutionRecoveryConflictError: If conflict_id is None
                or blank, resolution is None, no conflict is known
                under conflict_id, or it has already been resolved
        """

        self._validate_id(conflict_id, "conflict ID")

        if resolution is None:
            raise ExecutionRecoveryConflictError(
                f"Cannot resolve conflict ID {conflict_id!r} without an explicit resolution."
            )

        with self._lock:
            session_id = self._session_by_conflict.get(conflict_id)

            if session_id is None:
                raise ExecutionRecoveryConflictError(f"No conflict is known under conflict ID {conflict_id!r}.")

            resolved_ids = self._resolved_ids_by_session.setdefault(session_id, set())

            if conflict_id in resolved_ids:
                raise ExecutionRecoveryConflictError(f"Conflict ID {conflict_id!r} has already been resolved.")

            resolved_ids.add(conflict_id)

            return self._conflicts_by_session[session_id][conflict_id]

    def clear(self, session_id: str) -> None:
        """
        Discard a session's tracked conflicts. Refuses to do so
        while any remain unresolved.

        Raises:
            ExecutionRecoveryConflictError: If session_id is None or
                blank, or the session still has unresolved conflicts
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            if self.conflicts(session_id):
                raise ExecutionRecoveryConflictError(
                    f"Cannot clear session ID {session_id!r}: it still has unresolved conflicts."
                )

            self._discard(session_id)

    def _discard(self, session_id: str) -> None:
        for conflict_id in self._conflicts_by_session.pop(session_id, {}):
            self._session_by_conflict.pop(conflict_id, None)

        self._resolved_ids_by_session.pop(session_id, None)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryConflictError(f"Cannot use an empty or blank {field_name}.")
