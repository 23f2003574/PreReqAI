from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_artifact_consumption_lease_error import (
    ExecutionArtifactConsumptionLeaseError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "ACTIVE",
        "EXPIRED",
        "RELEASED",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionLease:
    """
    Immutable record of a consumer's temporary claim, within one
    consumption session, on continued access to a single artifact.

    The lease is a value object only. It performs no expiry or
    enforcement of its own; acquiring, renewing, releasing, and
    cleaning up leases is the responsibility of an execution artifact
    consumption lease service.

    Attributes:
        lease_id: The lease's unique identifier
        consumption_id: The identifier of the consumption session
            this lease belongs to
        artifact_id: The identifier of the leased artifact
        expires_at: When this lease stops being active on its own,
            absent a renewal
        status: The lease's current status, one of ACTIVE, EXPIRED,
            or RELEASED
    """

    consumption_id: str

    artifact_id: str

    expires_at: datetime

    lease_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    status: str = "ACTIVE"

    def __post_init__(self):
        self._require_text(self.lease_id, "lease ID")
        self._require_text(self.consumption_id, "consumption ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactConsumptionLeaseError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.expires_at, datetime):
            raise ExecutionArtifactConsumptionLeaseError(
                "Cannot build an execution artifact consumption lease with a non-datetime expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionLeaseError(
                f"Cannot build an execution artifact consumption lease with an empty or blank {field_name}."
            )
