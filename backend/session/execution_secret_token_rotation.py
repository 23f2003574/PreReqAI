from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_secret_token_rotation_error import (
    ExecutionSecretTokenRotationError,
)


@dataclass(frozen=True)
class ExecutionSecretTokenRotation:
    """
    Immutable record of a single execution secret token rotation.

    The rotation is a value object only. It performs no rotation of
    its own; rotating a principal's token, tracking which token is
    current, and revoking a rotation's previous token is the
    responsibility of an execution secret token rotation service.

    Attributes:
        rotation_id: The rotation's unique identifier
        secret_id: The identifier of the secret the rotated token
            grants access to
        previous_token_id: The token ID that was current immediately
            before this rotation, or None if this was the first
            rotation for the principal this rotation was performed
            for
        current_token_id: The token ID this rotation made current
        rotated_at: When this rotation occurred
    """

    rotation_id: str

    secret_id: str

    previous_token_id: str | None

    current_token_id: str

    rotated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.rotation_id, "rotation ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.current_token_id, "current token ID")

        if self.previous_token_id is not None and (
            not isinstance(self.previous_token_id, str) or not self.previous_token_id.strip()
        ):
            raise ExecutionSecretTokenRotationError(
                "Cannot build an execution secret token rotation with a blank previous_token_id."
            )

        if not isinstance(self.rotated_at, datetime):
            raise ExecutionSecretTokenRotationError(
                "Cannot build an execution secret token rotation with a non-datetime rotated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretTokenRotationError(
                f"Cannot build an execution secret token rotation with an empty or blank {field_name}."
            )
