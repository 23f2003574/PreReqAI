from dataclasses import (
    dataclass,
    field as dataclass_field,
)

from uuid import uuid4

from .execution_recovery_conflict_error import (
    ExecutionRecoveryConflictError,
)


@dataclass(frozen=True)
class ExecutionRecoveryConflict:
    """
    Immutable record of one field where a recovery checkpoint's
    captured value differs from the session's current runtime value.

    The conflict is a value object only. It performs no comparison
    or resolution of its own; comparing a checkpoint against current
    state, listing outstanding conflicts, recording an explicit
    resolution for one, and clearing a session's resolved conflicts
    is the responsibility of an execution recovery conflict service.

    Attributes:
        conflict_id: The conflict's unique identifier
        session_id: The identifier of the execution session the
            conflict was found in
        checkpoint_id: The identifier of the checkpoint compared
            against current state
        field: The name of the field that differs
        checkpoint_value: The field's value as captured in the
            checkpoint
        current_value: The field's current runtime value
    """

    session_id: str

    checkpoint_id: str

    field: str

    checkpoint_value: object

    current_value: object

    conflict_id: str = dataclass_field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.conflict_id, "conflict ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.field, "field")

        if self.checkpoint_value == self.current_value:
            raise ExecutionRecoveryConflictError(
                "Cannot build an execution recovery conflict where checkpoint_value equals current_value: "
                "there is no difference to report."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryConflictError(
                f"Cannot build an execution recovery conflict with an empty or blank {field_name}."
            )
