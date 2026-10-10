from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_certification_validity_error import (
    ExecutionCertificationValidityError,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_EXPIRED = "EXPIRED"

STATUS_INVALIDATED = "INVALIDATED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_INVALIDATED,
)


@dataclass(frozen=True)
class ExecutionCertificationValidity:
    """
    Immutable record of whether a compliance certification is still
    within its validity period and has not been invalidated.

    The record is a value object only. It performs no time tracking
    or invalidation of its own; checking, expiring, and invalidating
    a certification's validity is the responsibility of an execution
    certification validity service, which produces a new record for
    every transition rather than mutating an existing one.

    Attributes:
        certification_id: The identifier of the compliance
            certification this record tracks
        expires_at: When this certification's validity period ends
        status: The record's current state, one of STATUSES
        invalidated_at: When the record became EXPIRED or
            INVALIDATED, or None while it is still ACTIVE
        reason: Why the record was INVALIDATED, or None otherwise
    """

    certification_id: str

    expires_at: datetime

    status: str = STATUS_ACTIVE

    invalidated_at: datetime | None = None

    reason: str | None = None

    def __post_init__(self):
        self._require_text(self.certification_id, "certification ID")

        if not isinstance(self.expires_at, datetime):
            raise ExecutionCertificationValidityError(
                "Cannot build an execution certification validity record with no expires_at."
            )

        if self.status not in STATUSES:
            raise ExecutionCertificationValidityError(
                f"Cannot build an execution certification validity record with an unknown status: {self.status!r}."
            )

        is_active = self.status == STATUS_ACTIVE

        if is_active and self.invalidated_at is not None:
            raise ExecutionCertificationValidityError(
                "Cannot build an execution certification validity record: an active record cannot have an invalidated_at."
            )

        if not is_active and self.invalidated_at is None:
            raise ExecutionCertificationValidityError(
                "Cannot build an execution certification validity record: an expired or invalidated record must have an invalidated_at."
            )

        if self.status == STATUS_INVALIDATED:
            self._require_text(self.reason, "reason")
        elif self.reason is not None:
            raise ExecutionCertificationValidityError(
                "Cannot build an execution certification validity record: only an invalidated record can have a reason."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionCertificationValidityError(
                f"Cannot build an execution certification validity record with an empty or blank {field_name}."
            )
