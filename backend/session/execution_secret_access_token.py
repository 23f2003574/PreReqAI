from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_secret_token_error import (
    ExecutionSecretTokenError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "ACTIVE",
        "EXPIRED",
        "REVOKED",
    }
)

_FORBIDDEN_TOKEN_ID_MARKERS = (
    "://",
)


@dataclass(frozen=True)
class ExecutionSecretAccessToken:
    """
    Immutable, short-lived credential that stands in for direct,
    persistent access to a secret: a caller presents the token, not
    the secret's own reference, to prove it was authorized.

    The token is a value object only. It performs no validation of
    its own; issuing, validating, and revoking tokens is the
    responsibility of an execution secret token service. It never
    carries a raw secret value or reference: token_id is always an
    opaque identifier, unrelated to whatever the secret protects.

    Attributes:
        token_id: The token's unique, opaque identifier
        secret_id: The identifier of the secret this token grants
            access to
        principal: Who or what this token was issued to
        expires_at: When this token stops being active on its own
        status: The token's current status, one of ACTIVE, EXPIRED,
            or REVOKED
    """

    secret_id: str

    principal: str

    expires_at: datetime

    token_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    status: str = "ACTIVE"

    def __post_init__(self):
        self._require_text(self.token_id, "token ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.principal, "principal")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionSecretTokenError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.expires_at, datetime):
            raise ExecutionSecretTokenError(
                "Cannot build an execution secret access token with a non-datetime expires_at."
            )

        if self.token_id == self.secret_id or any(
            marker in self.token_id for marker in _FORBIDDEN_TOKEN_ID_MARKERS
        ):
            raise ExecutionSecretTokenError(
                "Cannot build an execution secret access token whose token_id carries a raw secret "
                "value or reference."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionSecretTokenError(
                f"Cannot build an execution secret access token with an empty or blank {field_name}."
            )
