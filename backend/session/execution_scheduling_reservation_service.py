from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_job import (
    STATUS_QUEUED,
)

from .execution_scheduling_reservation import (
    ExecutionSchedulingReservation,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_RELEASED,
)

from .execution_scheduling_reservation_error import (
    ExecutionSchedulingReservationError,
)

DEFAULT_TTL_SECONDS = 60


class ExecutionSchedulingReservationService:
    """
    Reserves scheduler capacity for a specific job so another
    scheduler cannot claim it concurrently.

    Composes with an existing job status-tracking service (anything
    exposing `status(job_id)`, matching ExecutionJobQueueService),
    used to confirm a job is QUEUED, and therefore eligible, before it
    can be reserved.

    Behavior:
    - acquire() admits a new ACTIVE reservation, but only for a job
      that is currently QUEUED and does not already have an active
      reservation held by any scheduler
    - A reservation stops blocking other schedulers once it is
      released, or once its expires_at passes, even before expired()
      is next called to sweep it
    - renew() extends an active reservation's expires_at, keeping the
      claim alive
    - release() is idempotent: releasing an already-released or
      already-expired reservation is a no-op, not an error
    - expired() transitions every reservation whose expires_at has
      passed from ACTIVE to EXPIRED, freeing its job for reservation

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, status_service):
        self._status_service = status_service
        self._reservations_by_id = {}
        self._lock = RLock()

    def acquire(
        self, job_id: str, scheduler_id: str, ttl_seconds: float = DEFAULT_TTL_SECONDS
    ) -> ExecutionSchedulingReservation:
        """
        Claim exclusive scheduling rights over job_id on behalf of
        scheduler_id.

        Raises:
            ExecutionSchedulingReservationError: If job_id or
                scheduler_id is None or blank, job_id is unknown or
                not currently QUEUED, or job_id already has an active
                reservation
        """

        self._validate_text(job_id, "job ID")
        self._validate_text(scheduler_id, "scheduler ID")

        try:
            status = self._status_service.status(job_id)
        except Exception as error:
            raise ExecutionSchedulingReservationError(
                f"Cannot reserve job ID {job_id!r}: it is unknown."
            ) from error

        if status != STATUS_QUEUED:
            raise ExecutionSchedulingReservationError(
                f"Cannot reserve job ID {job_id!r}: it is not eligible (status is {status!r})."
            )

        with self._lock:
            if self.active(job_id) is not None:
                raise ExecutionSchedulingReservationError(
                    f"Cannot reserve job ID {job_id!r}: it already has an active reservation."
                )

            reservation = ExecutionSchedulingReservation(
                reservation_id=str(uuid4()),
                job_id=job_id,
                scheduler_id=scheduler_id,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
                status=STATUS_ACTIVE,
            )

            self._reservations_by_id[reservation.reservation_id] = reservation

            return reservation

    def renew(
        self, reservation_id: str, ttl_seconds: float = DEFAULT_TTL_SECONDS
    ) -> ExecutionSchedulingReservation:
        """
        Extend an active reservation's expiry.

        Raises:
            ExecutionSchedulingReservationError: If reservation_id is
                None or blank, no reservation is registered under it,
                or it is not currently active
        """

        self._validate_text(reservation_id, "reservation ID")

        with self._lock:
            reservation = self._resolve(reservation_id)

            if not self._is_active(reservation):
                raise ExecutionSchedulingReservationError(
                    f"Cannot renew reservation ID {reservation_id!r}: it is not active."
                )

            renewed = replace(
                reservation,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            )

            self._reservations_by_id[reservation_id] = renewed

            return renewed

    def release(self, reservation_id: str) -> ExecutionSchedulingReservation:
        """
        Release a reservation's claim. Idempotent: releasing an
        already-released or already-expired reservation simply
        returns it unchanged.

        Raises:
            ExecutionSchedulingReservationError: If reservation_id is
                None or blank, or no reservation is registered under
                it
        """

        self._validate_text(reservation_id, "reservation ID")

        with self._lock:
            reservation = self._resolve(reservation_id)

            if reservation.status != STATUS_ACTIVE:
                return reservation

            released = replace(reservation, status=STATUS_RELEASED)
            self._reservations_by_id[reservation_id] = released

            return released

    def active(self, job_id: str):
        """
        The currently active reservation held for job_id, or None if
        none.
        """

        self._validate_text(job_id, "job ID")

        with self._lock:
            for reservation in self._reservations_by_id.values():
                if reservation.job_id == job_id and self._is_active(reservation):
                    return reservation

            return None

    def expired(self) -> tuple:
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

    @staticmethod
    def _is_active(reservation: ExecutionSchedulingReservation) -> bool:
        return reservation.status == STATUS_ACTIVE and reservation.expires_at > datetime.now(timezone.utc)

    def _resolve(self, reservation_id: str) -> ExecutionSchedulingReservation:
        reservation = self._reservations_by_id.get(reservation_id)

        if reservation is None:
            raise ExecutionSchedulingReservationError(
                f"No reservation is recorded under reservation ID {reservation_id!r}."
            )

        return reservation

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulingReservationError(f"Cannot use an empty or blank {field_name}.")
