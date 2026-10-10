from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_secret_error import (
    ExecutionSecretError,
)


@dataclass(frozen=True)
class ExecutionSecret:
    """
    Immutable record of an execution-scoped secret, stored separately
    from runtime configuration.

    The secret never carries a raw value. It only carries a
    value_ref: an opaque reference the caller resolves against
    whatever backs the secret (e.g. a vault path or credential
    handle), so a registered ExecutionSecret can be freely returned
    from lookups without exposing what it actually protects.

    The secret is a value object only. It performs no storage,
    expiry, or revocation of its own; registering, retrieving, and
    removing secrets is the responsibility of an execution secret
    service.

    Attributes:
        secret_id: The secret's unique identifier
        session_id: The identifier of the execution session this
            secret is scoped to
        name: The secret's name, unique within its session
        value_ref: An opaque reference to the secret's value, never
            the raw value itself
        created_at: When this secret was registered
        expires_at: When this secret stops being available, or None
            if it never expires
    """

    secret_id: str

    session_id: str

    name: str

    value_ref: str

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    expires_at: datetime | None = None

    def __post_init__(self):
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.name, "name")
        self._require_text(self.value_ref, "value ref")

        if not isinstance(self.created_at, datetime):
            raise ExecutionSecretError(
                "Cannot build an execution secret with a non-datetime created_at."
            )

        if self.expires_at is not None and not isinstance(self.expires_at, datetime):
            raise ExecutionSecretError(
                "Cannot build an execution secret with a non-datetime expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretError(
                f"Cannot build an execution secret with an empty or blank {field_name}."
            )
