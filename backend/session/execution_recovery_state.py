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

from .execution_recovery_state_error import (
    ExecutionRecoveryStateError,
)


@dataclass(frozen=True)
class ExecutionRecoveryState:
    """
    Immutable runtime state reconstructed from a validated recovery
    checkpoint, ready to be applied to resume an interrupted
    execution session.

    The state is a value object only. It performs no reconstruction
    or application of its own; rebuilding it from a checkpoint,
    looking it up, applying it, and clearing it is the
    responsibility of an execution recovery state service.

    Attributes:
        session_id: The identifier of the execution session this
            state resumes
        checkpoint_id: The identifier of the checkpoint this state
            was reconstructed from
        stage_id: The identifier of the stage the session resumes at
        variables: The reconstructed runtime variables, preserved
            exactly from the checkpoint's captured state, as an
            immutable mapping
        restored_at: When this state was reconstructed
    """

    session_id: str

    checkpoint_id: str

    stage_id: str

    variables: Mapping

    restored_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.stage_id, "stage ID")

        if not isinstance(self.restored_at, datetime):
            raise ExecutionRecoveryStateError(
                "Cannot build an execution recovery state with a non-datetime restored_at."
            )

        if not isinstance(self.variables, Mapping):
            raise ExecutionRecoveryStateError(
                "Cannot build an execution recovery state with a non-mapping variables."
            )

        object.__setattr__(self, "variables", MappingProxyType(dict(self.variables)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryStateError(
                f"Cannot build an execution recovery state with an empty or blank {field_name}."
            )
