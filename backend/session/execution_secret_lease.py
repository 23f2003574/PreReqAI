from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_secret_lease_error import (
    ExecutionSecretLeaseError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "ACTIVE",
        "EXPIRED",
        "RELEASED",
    }
)


@dataclass(frozen=True)
class ExecutionSecretLease:
    """
    Immutable record of a principal's temporary grant of access to a
    secret.

    The lease is a value object only. It performs no expiry or
    enforcement of its own; acquiring, renewing, releasing, and
    cleaning up leases is the responsibility of an execution secret
    lease service.

    Attributes:
        lease_id: The lease's unique identifier
        secret_id: The identifier of the leased secret
        principal: Who or what holds this lease
        expires_at: When this lease stops being active on its own,
            absent a renewal
        status: The lease's current status, one of ACTIVE, EXPIRED,
            or RELEASED
    """

    secret_id: str

    principal: str

    expires_at: datetime

    lease_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    status: str = "ACTIVE"

    def __post_init__(self):
        self._require_text(self.lease_id, "lease ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.principal, "principal")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionSecretLeaseError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.expires_at, datetime):
            raise ExecutionSecretLeaseError(
                "Cannot build an execution secret lease with a non-datetime expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionSecretLeaseError(
                f"Cannot build an execution secret lease with an empty or blank {field_name}."
            )
