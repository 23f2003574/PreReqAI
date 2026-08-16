from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from numbers import (
    Real,
)

from .execution_resource_reservation_error import (
    ExecutionResourceReservationError,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_RELEASED = "RELEASED"

STATUS_EXPIRED = "EXPIRED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_RELEASED,
    STATUS_EXPIRED,
)


@dataclass(frozen=True)
class ExecutionResourceReservation:
    """
    Immutable record of a claim on some amount of a scarce execution
    resource, held on behalf of a job until it is released or
    expires.

    The reservation is a value object only. It performs no capacity
    accounting of its own; reserving, releasing, and expiring
    reservations is the responsibility of an execution resource
    reservation service.

    Attributes:
        reservation_id: The reservation's unique identifier
        job_id: The identifier of the job the reservation is held for
        resource_type: The kind of resource reserved
        amount: How much of resource_type is reserved. Must be
            positive
        status: The reservation's current state, one of STATUSES
        expires_at: When the reservation stops holding capacity
            unless released first
    """

    reservation_id: str

    job_id: str

    resource_type: str

    amount: float

    status: str = STATUS_ACTIVE

    expires_at: datetime = None

    def __post_init__(self):
        self._require_text(self.reservation_id, "reservation ID")
        self._require_text(self.job_id, "job ID")
        self._require_text(self.resource_type, "resource type")

        if not isinstance(self.amount, Real) or isinstance(self.amount, bool):
            raise ExecutionResourceReservationError(
                "Cannot build an execution resource reservation with a non-numeric amount."
            )

        if self.amount <= 0:
            raise ExecutionResourceReservationError(
                "Cannot build an execution resource reservation with a non-positive amount."
            )

        if self.status not in STATUSES:
            raise ExecutionResourceReservationError(
                f"Cannot build an execution resource reservation with an unknown status: {self.status!r}."
            )

        if self.expires_at is None or not isinstance(self.expires_at, datetime):
            raise ExecutionResourceReservationError(
                "Cannot build an execution resource reservation with a non-datetime expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionResourceReservationError(
                f"Cannot build an execution resource reservation with an empty or blank {field_name}."
            )
