from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_compliance_renewal_error import (
    ExecutionComplianceRenewalError,
)


@dataclass(frozen=True)
class ExecutionComplianceRenewal:
    """
    Immutable record of a reviewer extending a certification's
    validity period after review, without erasing or replacing the
    certification's prior history.

    The renewal is a value object only. It performs no eligibility
    checking of its own; confirming a certification is renewable and
    recording a renewal is the responsibility of an execution
    compliance renewal service. Every renewal is retained as its own
    record: renewing a certification again never edits or removes an
    earlier renewal record.

    Attributes:
        renewal_id: The renewal's unique identifier
        certification_id: The identifier of the certification renewed
        reviewer: The identifier of the authorized reviewer who
            performed the renewal
        previous_expiry: The certification's expiry immediately
            before this renewal
        new_expiry: The certification's expiry after this renewal.
            Always later than previous_expiry
        renewed_at: When this renewal was recorded
    """

    renewal_id: str

    certification_id: str

    reviewer: str

    previous_expiry: datetime

    new_expiry: datetime

    renewed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.renewal_id, "renewal ID")
        self._require_text(self.certification_id, "certification ID")
        self._require_text(self.reviewer, "reviewer")

        if not isinstance(self.previous_expiry, datetime):
            raise ExecutionComplianceRenewalError(
                "Cannot build an execution compliance renewal with a non-datetime previous_expiry."
            )

        if not isinstance(self.new_expiry, datetime):
            raise ExecutionComplianceRenewalError(
                "Cannot build an execution compliance renewal with a non-datetime new_expiry."
            )

        if self.new_expiry <= self.previous_expiry:
            raise ExecutionComplianceRenewalError(
                "Cannot build an execution compliance renewal: new_expiry must be later than previous_expiry."
            )

        if not isinstance(self.renewed_at, datetime):
            raise ExecutionComplianceRenewalError(
                "Cannot build an execution compliance renewal with a non-datetime renewed_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceRenewalError(
                f"Cannot build an execution compliance renewal with an empty or blank {field_name}."
            )
