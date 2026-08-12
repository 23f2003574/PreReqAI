from threading import (
    RLock,
)

from .execution_recovery_validation_error import (
    ExecutionRecoveryValidationError,
)

from .execution_recovery_validation import (
    ExecutionRecoveryValidation,
)


class ExecutionRecoveryValidationService:
    """
    Validates recovery checkpoints before they are restored from.

    Checkpoints, session statuses, and a session's known stages are
    assumed to already exist elsewhere; this service depends on
    plain resolver callables for them rather than a concrete store:
    - checkpoint_resolver(checkpoint_id) -> checkpoint or None
    - session_checkpoints_resolver(session_id) -> mapping of
      stage_id to that stage's latest checkpoint
    - session_status_resolver(session_id) -> status string or None
    - session_stage_resolver(session_id) -> the session's known
      stage IDs, or None/empty if the session is unknown

    Behavior:
    - validate() checks one checkpoint, by ID, against every rule
      below, always in the same order, so the resulting violations
      are deterministic
    - validate_session() checks every stage's latest checkpoint for
      a session, ordered by stage ID
    - invalid() narrows validate_session() to only the checkpoints
      that failed
    - report() summarizes validate_session() as counts alongside the
      individual validations

    Rules checked, in order:
    - The checkpoint's session must be known and must not have
      COMPLETED; a completed session cannot be recovered into
    - The checkpoint's stage must be one of the session's known
      stages
    - The checkpoint's captured state must not be empty

    validate() and validate_session() never raise for a checkpoint
    that fails these rules; failure is reported as violations on the
    returned ExecutionRecoveryValidation instead.

    The service is:
    - Thread-safe: All reads are guarded by an internal lock
    """

    def __init__(
        self,
        checkpoint_resolver,
        session_checkpoints_resolver,
        session_status_resolver,
        session_stage_resolver,
    ):
        self._checkpoint_resolver = checkpoint_resolver
        self._session_checkpoints_resolver = session_checkpoints_resolver
        self._session_status_resolver = session_status_resolver
        self._session_stage_resolver = session_stage_resolver
        self._lock = RLock()

    def validate(self, checkpoint_id: str) -> ExecutionRecoveryValidation:
        """
        Check one checkpoint, by ID, against every validation rule.

        Raises:
            ExecutionRecoveryValidationError: If checkpoint_id is
                None or blank, or no checkpoint is known under it
        """

        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._checkpoint_resolver(checkpoint_id)

            if checkpoint is None:
                raise ExecutionRecoveryValidationError(f"No checkpoint is known under checkpoint ID {checkpoint_id!r}.")

            return self._build(checkpoint)

    def validate_session(self, session_id: str) -> tuple:
        """
        Check every stage's latest checkpoint for a session, ordered
        by stage ID.

        Raises:
            ExecutionRecoveryValidationError: If session_id is None
                or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            checkpoints_by_stage = self._session_checkpoints_resolver(session_id) or {}

            return tuple(self._build(checkpoints_by_stage[stage_id]) for stage_id in sorted(checkpoints_by_stage))

    def invalid(self, session_id: str) -> tuple:
        """
        Narrow validate_session() to only the checkpoints that
        failed validation.

        Raises:
            ExecutionRecoveryValidationError: If session_id is None
                or blank
        """

        return tuple(validation for validation in self.validate_session(session_id) if not validation.valid)

    def report(self, session_id: str) -> dict:
        """
        Summarize validate_session() for a session as pass/fail
        counts alongside the individual validations.

        Raises:
            ExecutionRecoveryValidationError: If session_id is None
                or blank
        """

        validations = self.validate_session(session_id)

        valid_count = sum(1 for validation in validations if validation.valid)

        return {
            "session_id": session_id,
            "total": len(validations),
            "valid_count": valid_count,
            "invalid_count": len(validations) - valid_count,
            "validations": validations,
        }

    def _build(self, checkpoint) -> ExecutionRecoveryValidation:
        violations = []

        status = self._session_status_resolver(checkpoint.session_id)

        if status is None:
            violations.append(f"Session {checkpoint.session_id!r} is unknown.")
        elif status == "COMPLETED":
            violations.append(
                f"Session {checkpoint.session_id!r} has already COMPLETED; recovery is not permitted."
            )

        valid_stage_ids = self._session_stage_resolver(checkpoint.session_id) or frozenset()

        if checkpoint.stage_id not in valid_stage_ids:
            violations.append(
                f"Stage {checkpoint.stage_id!r} is not a known stage for session {checkpoint.session_id!r}."
            )

        if not checkpoint.state:
            violations.append(f"Checkpoint {checkpoint.checkpoint_id!r} has no captured state.")

        return ExecutionRecoveryValidation(
            checkpoint_id=checkpoint.checkpoint_id,
            valid=not violations,
            violations=tuple(violations),
        )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryValidationError(f"Cannot use an empty or blank {field_name}.")
