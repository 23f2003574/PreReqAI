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

from .execution_recovery_checkpoint_error import (
    ExecutionRecoveryCheckpointError,
)


@dataclass(frozen=True)
class ExecutionRecoveryCheckpoint:
    """
    Immutable snapshot of the minimum state required to resume an
    interrupted execution session at a given stage.

    The checkpoint is a value object only. It performs no capture or
    restoration of its own; creating a checkpoint, finding the
    latest one for a stage, and restoring from one is the
    responsibility of an execution recovery checkpoint service.

    Attributes:
        checkpoint_id: The checkpoint's unique identifier
        session_id: The identifier of the execution session the
            checkpoint belongs to
        stage_id: The identifier of the stage within the session the
            checkpoint captures
        state: The captured state needed to resume the session at
            this stage, as an immutable mapping
        created_at: When this checkpoint was created
    """

    session_id: str

    stage_id: str

    state: Mapping

    checkpoint_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.stage_id, "stage ID")

        if not isinstance(self.created_at, datetime):
            raise ExecutionRecoveryCheckpointError(
                "Cannot build an execution recovery checkpoint with a non-datetime created_at."
            )

        if not isinstance(self.state, Mapping):
            raise ExecutionRecoveryCheckpointError(
                "Cannot build an execution recovery checkpoint with a non-mapping state."
            )

        object.__setattr__(self, "state", MappingProxyType(dict(self.state)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryCheckpointError(
                f"Cannot build an execution recovery checkpoint with an empty or blank {field_name}."
            )
