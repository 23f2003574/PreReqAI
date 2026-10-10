from collections.abc import (
    Mapping,
)

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from types import (
    MappingProxyType,
)

from uuid import uuid4

from .execution_recovery_rollback_error import (
    ExecutionRecoveryRollbackError,
)


@dataclass(frozen=True)
class ExecutionRecoveryRollback:
    """
    Immutable snapshot of a session's pre-recovery state, captured
    so a partially applied recovery can be safely undone.

    The rollback is a value object only. It performs no undoing of
    its own; preparing a snapshot, executing the rollback, checking
    its status, and restoring the preserved state is the
    responsibility of an execution recovery rollback service.

    Attributes:
        rollback_id: The rollback's unique identifier
        session_id: The identifier of the execution session this
            rollback is for
        checkpoint_id: The identifier of the checkpoint the active
            recovery attempt was using
        state: The session's runtime state exactly as it stood
            before recovery began, as an immutable mapping
        created_at: When this rollback was prepared
    """

    session_id: str

    checkpoint_id: str

    state: Mapping

    rollback_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.rollback_id, "rollback ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")

        if not isinstance(self.created_at, datetime):
            raise ExecutionRecoveryRollbackError(
                "Cannot build an execution recovery rollback with a non-datetime created_at."
            )

        if not isinstance(self.state, Mapping):
            raise ExecutionRecoveryRollbackError(
                "Cannot build an execution recovery rollback with a non-mapping state."
            )

        object.__setattr__(self, "state", MappingProxyType(dict(self.state)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryRollbackError(
                f"Cannot build an execution recovery rollback with an empty or blank {field_name}."
            )
