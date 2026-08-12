from threading import (
    RLock,
)

from .execution_recovery_checkpoint_error import (
    ExecutionRecoveryCheckpointError,
)

from .execution_recovery_checkpoint import (
    ExecutionRecoveryCheckpoint,
)


class ExecutionRecoveryCheckpointService:
    """
    Captures and restores the minimum state required to resume an
    interrupted execution session.

    A checkpoint is captured per (session, stage) pair. A session
    status resolver supplied at construction time reports a
    session's current status; it is assumed to already exist, and is
    used only to confirm a session is INTERRUPTED before restoring
    from one of its checkpoints.

    Behavior:
    - create() captures a new checkpoint for a session's stage; it
      becomes that stage's latest checkpoint
    - latest() looks up, for a session, the most recent checkpoint
      recorded per stage
    - restore() returns the checkpoint captured for resuming, but
      only for a session the resolver reports as INTERRUPTED
    - delete() permanently removes a checkpoint

    Checkpoints are immutable once created: create() is the only way
    to produce one, and none of its fields can be changed afterward.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, session_status_resolver):
        self._session_status_resolver = session_status_resolver
        self._checkpoints_by_id = {}
        self._latest_id_by_session_stage = {}
        self._lock = RLock()

    def create(self, session_id: str, stage_id: str, state) -> ExecutionRecoveryCheckpoint:
        """
        Capture a new checkpoint for a session's stage, becoming
        that stage's latest checkpoint.

        Raises:
            ExecutionRecoveryCheckpointError: If session_id or
                stage_id is None or blank, or state is not a mapping
        """

        with self._lock:
            checkpoint = ExecutionRecoveryCheckpoint(session_id=session_id, stage_id=stage_id, state=state)

            self._checkpoints_by_id[checkpoint.checkpoint_id] = checkpoint
            self._latest_id_by_session_stage[(session_id, stage_id)] = checkpoint.checkpoint_id

            return checkpoint

    def latest(self, session_id: str) -> dict:
        """
        Look up the most recent checkpoint recorded for each of a
        session's stages.

        Raises:
            ExecutionRecoveryCheckpointError: If session_id is None
                or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return {
                stage_id: self._checkpoints_by_id[checkpoint_id]
                for (sid, stage_id), checkpoint_id in self._latest_id_by_session_stage.items()
                if sid == session_id
            }

    def restore(self, checkpoint_id: str) -> ExecutionRecoveryCheckpoint:
        """
        Return the checkpoint to resume from, provided the
        checkpoint's session is currently INTERRUPTED.

        Raises:
            ExecutionRecoveryCheckpointError: If checkpoint_id is
                None or blank, no checkpoint is known under it, its
                session is unknown to the session status resolver,
                or that session is not INTERRUPTED
        """

        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._resolve(checkpoint_id)

            status = self._session_status_resolver(checkpoint.session_id)

            if status is None:
                raise ExecutionRecoveryCheckpointError(
                    f"No session is known under session ID {checkpoint.session_id!r}."
                )

            if status != "INTERRUPTED":
                raise ExecutionRecoveryCheckpointError(
                    f"Cannot restore checkpoint ID {checkpoint_id!r}: session {checkpoint.session_id!r} is "
                    f"{status}, not INTERRUPTED."
                )

            return checkpoint

    def delete(self, checkpoint_id: str) -> None:
        """
        Permanently remove a checkpoint.

        Raises:
            ExecutionRecoveryCheckpointError: If checkpoint_id is
                None or blank, or no checkpoint is known under it
        """

        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._resolve(checkpoint_id)

            del self._checkpoints_by_id[checkpoint_id]

            key = (checkpoint.session_id, checkpoint.stage_id)

            if self._latest_id_by_session_stage.get(key) == checkpoint_id:
                del self._latest_id_by_session_stage[key]

    def _resolve(self, checkpoint_id: str) -> ExecutionRecoveryCheckpoint:
        checkpoint = self._checkpoints_by_id.get(checkpoint_id)

        if checkpoint is None:
            raise ExecutionRecoveryCheckpointError(f"No checkpoint is known under checkpoint ID {checkpoint_id!r}.")

        return checkpoint

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryCheckpointError(f"Cannot use an empty or blank {field_name}.")
