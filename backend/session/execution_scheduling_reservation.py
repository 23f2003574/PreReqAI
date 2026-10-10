from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_scheduling_reservation_error import (
    ExecutionSchedulingReservationError,
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
class ExecutionSchedulingReservation:
    """
    Immutable record that a single scheduler has claimed the
    exclusive right to schedule a job, until it releases the claim or
    the claim expires.

    The reservation is a value object only. It performs no claim
    accounting of its own; acquiring, renewing, releasing, and
    expiring reservations is the responsibility of an execution
    scheduling reservation service, which produces a new record for
    every transition rather than mutating an existing one.

    Attributes:
        reservation_id: The reservation's unique identifier
        job_id: The identifier of the job claimed
        scheduler_id: The identifier of the scheduler holding the
            claim
        expires_at: When the claim lapses unless renewed first
        status: The reservation's current state, one of STATUSES
    """

    reservation_id: str

    job_id: str

    scheduler_id: str

    expires_at: datetime

    status: str = STATUS_ACTIVE

    def __post_init__(self):
        self._require_text(self.reservation_id, "reservation ID")
        self._require_text(self.job_id, "job ID")
        self._require_text(self.scheduler_id, "scheduler ID")

        if self.expires_at is None or not isinstance(self.expires_at, datetime):
            raise ExecutionSchedulingReservationError(
                "Cannot build an execution scheduling reservation with a non-datetime expires_at."
            )

        if self.status not in STATUSES:
            raise ExecutionSchedulingReservationError(
                f"Cannot build an execution scheduling reservation with an unknown status: {self.status!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulingReservationError(
                f"Cannot build an execution scheduling reservation with an empty or blank {field_name}."
            )
