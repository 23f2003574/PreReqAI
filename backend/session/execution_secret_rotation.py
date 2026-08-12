from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_secret_rotation_error import (
    ExecutionSecretRotationError,
)


@dataclass(frozen=True)
class ExecutionSecretRotation:
    """
    Immutable record of a single execution secret rotation.

    The rotation is a value object only. It performs no rotation of
    its own; rotating a secret, tracking its current reference, and
    rolling a rotation back is the responsibility of an execution
    secret rotation service.

    Attributes:
        rotation_id: The rotation's unique identifier
        secret_id: The identifier of the secret that was rotated
        previous_ref: The value_ref that was active immediately
            before this rotation, or None if this was the secret's
            first rotation. Kept only to support rollback; it is
            never itself the active reference once this rotation has
            taken effect
        current_ref: The value_ref this rotation made active
        rotated_at: When this rotation occurred
    """

    rotation_id: str

    secret_id: str

    previous_ref: str | None

    current_ref: str

    rotated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.rotation_id, "rotation ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.current_ref, "current ref")

        if self.previous_ref is not None and (
            not isinstance(self.previous_ref, str) or not self.previous_ref.strip()
        ):
            raise ExecutionSecretRotationError(
                "Cannot build an execution secret rotation with a blank previous_ref."
            )

        if not isinstance(self.rotated_at, datetime):
            raise ExecutionSecretRotationError(
                "Cannot build an execution secret rotation with a non-datetime rotated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretRotationError(
                f"Cannot build an execution secret rotation with an empty or blank {field_name}."
            )
