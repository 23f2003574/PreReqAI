from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_secret_revocation_error import (
    ExecutionSecretRevocationError,
)


@dataclass(frozen=True)
class ExecutionSecretRevocation:
    """
    Immutable record of a single execution secret revocation.

    The revocation is a value object only. It performs no
    enforcement of its own; revoking a secret, invalidating its
    active leases, checking its revoked status, and restoring it is
    the responsibility of an execution secret revocation service.

    Attributes:
        revocation_id: The revocation's unique identifier
        secret_id: The identifier of the secret that was revoked
        reason: Why the secret was revoked
        revoked_at: When the secret was revoked
        revoked_by: Who or what revoked the secret
    """

    secret_id: str

    reason: str

    revoked_by: str

    revocation_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    revoked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.revocation_id, "revocation ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.reason, "reason")
        self._require_text(self.revoked_by, "revoked by")

        if not isinstance(self.revoked_at, datetime):
            raise ExecutionSecretRevocationError(
                "Cannot build an execution secret revocation with a non-datetime revoked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretRevocationError(
                f"Cannot build an execution secret revocation with an empty or blank {field_name}."
            )
