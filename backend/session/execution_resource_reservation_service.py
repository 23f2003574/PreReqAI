from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from numbers import (
    Real,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_resource_reservation import (
    ExecutionResourceReservation,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_RELEASED,
)

from .execution_resource_reservation_error import (
    ExecutionResourceReservationError,
)

DEFAULT_TTL_SECONDS = 300


class ExecutionResourceReservationService:
    """
    Reserves scarce execution resources (for example, GPU slots or
    memory) for queued jobs before they start.

    Each resource_type has a fixed total capacity, provided at
    construction time.

    Behavior:
    - reserve() admits a new ACTIVE reservation, but only if the
      resource has enough spare capacity and the job does not already
      hold an active reservation for that resource type
    - A reservation stops counting toward usage once it is released,
      or once its expires_at passes, even before expire() is next
      called to sweep it
    - expire() transitions every reservation whose expires_at has
      passed from ACTIVE to EXPIRED, releasing its capacity for good

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, capacity_by_resource: dict):
        if capacity_by_resource is None:
            raise ExecutionResourceReservationError(
                "Cannot initialize a resource reservation service with a None capacity_by_resource."
            )

        for resource_type, capacity in capacity_by_resource.items():
            if not isinstance(capacity, Real) or isinstance(capacity, bool) or capacity <= 0:
                raise ExecutionResourceReservationError(
                    f"Cannot initialize a resource reservation service: capacity for {resource_type!r} "
                    "must be a positive number."
                )

        self._capacity_by_resource = dict(capacity_by_resource)
        self._reservations_by_id = {}
        self._lock = RLock()

    def reserve(
        self,
        job_id: str,
        resource_type: str,
        amount: float,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> ExecutionResourceReservation:
        """
        Reserve amount of resource_type on behalf of job_id.

        Raises:
            ExecutionResourceReservationError: If job_id or
                resource_type is None or blank, resource_type has no
                configured capacity, amount is not a positive number,
                job_id already holds an active reservation for
                resource_type, or granting amount would exceed the
                resource's available capacity
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(resource_type, "resource type")

        if resource_type not in self._capacity_by_resource:
            raise ExecutionResourceReservationError(
                f"Cannot reserve unknown resource type {resource_type!r}."
            )

        if not isinstance(amount, Real) or isinstance(amount, bool) or amount <= 0:
            raise ExecutionResourceReservationError(
                "Cannot reserve a non-positive amount."
            )

        with self._lock:
            for reservation in self._reservations_by_id.values():
                if (
                    reservation.job_id == job_id
                    and reservation.resource_type == resource_type
                    and self._is_active(reservation)
                ):
                    raise ExecutionResourceReservationError(
                        f"Job ID {job_id!r} already holds an active reservation for resource type "
                        f"{resource_type!r}."
                    )

            if self._used(resource_type) + amount > self._capacity_by_resource[resource_type]:
                raise ExecutionResourceReservationError(
                    f"Cannot reserve {amount} of resource type {resource_type!r}: available capacity "
                    "is exhausted."
                )

            reservation = ExecutionResourceReservation(
                reservation_id=str(uuid4()),
                job_id=job_id,
                resource_type=resource_type,
                amount=amount,
                status=STATUS_ACTIVE,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            )

            self._reservations_by_id[reservation.reservation_id] = reservation

            return reservation

    def release(self, reservation_id: str) -> ExecutionResourceReservation:
        """
        Release a reservation's held capacity.

        Raises:
            ExecutionResourceReservationError: If reservation_id is
                None or blank, no reservation is registered under it,
                or it is not currently ACTIVE
        """

        self._validate_text(reservation_id, "reservation ID")

        with self._lock:
            reservation = self._resolve(reservation_id)

            if not self._is_active(reservation):
                raise ExecutionResourceReservationError(
                    f"Cannot release reservation ID {reservation_id!r}: it is not active."
                )

            released = replace(reservation, status=STATUS_RELEASED)
            self._reservations_by_id[reservation_id] = released

            return released

    def available(self, resource_type: str) -> float:
        """
        The spare capacity currently available for resource_type.

        Raises:
            ExecutionResourceReservationError: If resource_type is
                None or blank, or it has no configured capacity
        """

        self._validate_text(resource_type, "resource type")

        if resource_type not in self._capacity_by_resource:
            raise ExecutionResourceReservationError(
                f"Cannot check availability for unknown resource type {resource_type!r}."
            )

        with self._lock:
            return self._capacity_by_resource[resource_type] - self._used(resource_type)

    def active(self, job_id: str) -> tuple:
        """
        Every currently active reservation held for job_id.
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            return tuple(
                reservation
                for reservation in self._reservations_by_id.values()
                if reservation.job_id == job_id and self._is_active(reservation)
            )

    def expire(self) -> tuple:
        """
        Transition every reservation whose expires_at has passed from
        ACTIVE to EXPIRED.

        Returns:
            The reservations newly transitioned to EXPIRED
        """

        with self._lock:
            now = datetime.now(timezone.utc)
            newly_expired = []

            for reservation_id, reservation in list(self._reservations_by_id.items()):
                if reservation.status == STATUS_ACTIVE and reservation.expires_at <= now:
                    expired = replace(reservation, status=STATUS_EXPIRED)
                    self._reservations_by_id[reservation_id] = expired
                    newly_expired.append(expired)

            return tuple(newly_expired)

    def _used(self, resource_type: str) -> float:
        return sum(
            reservation.amount
            for reservation in self._reservations_by_id.values()
            if reservation.resource_type == resource_type and self._is_active(reservation)
        )

    @staticmethod
    def _is_active(reservation: ExecutionResourceReservation) -> bool:
        return reservation.status == STATUS_ACTIVE and reservation.expires_at > datetime.now(timezone.utc)

    def _resolve(self, reservation_id: str) -> ExecutionResourceReservation:
        reservation = self._reservations_by_id.get(reservation_id)

        if reservation is None:
            raise ExecutionResourceReservationError(
                f"No reservation is recorded under reservation ID {reservation_id!r}."
            )

        return reservation

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionResourceReservationError(f"Cannot use an empty or blank {field_name}.")
