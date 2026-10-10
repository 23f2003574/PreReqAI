import pytest

from backend.session import (
    ExecutionSchedulingReservation,
    ExecutionSchedulingReservationError as Error,
    ExecutionSchedulingReservationService,
)


class _FakeStatusService:
    def __init__(self, status_by_job=None):
        self._status_by_job = dict(status_by_job or {})

    def status(self, job_id):
        if job_id not in self._status_by_job:
            raise ValueError(f"unknown job {job_id!r}")

        return self._status_by_job[job_id]


def _build(status_by_job=None):
    status_service = _FakeStatusService(status_by_job or {"job-1": "QUEUED", "job-2": "QUEUED"})
    return status_service, ExecutionSchedulingReservationService(status_service)


class TestExecutionSchedulingReservationService:
    def test_acquire_and_release(self):
        _, service = _build()

        reservation = service.acquire("job-1", "scheduler-a")

        assert isinstance(reservation, ExecutionSchedulingReservation)
        assert reservation.status == "ACTIVE"
        assert service.active("job-1").reservation_id == reservation.reservation_id

        released = service.release(reservation.reservation_id)

        assert released.status == "RELEASED"
        assert service.active("job-1") is None

    def test_release_idempotency(self):
        _, service = _build()
        reservation = service.acquire("job-1", "scheduler-a")

        first = service.release(reservation.reservation_id)
        second = service.release(reservation.reservation_id)

        assert first.status == "RELEASED"
        assert second.status == "RELEASED"

    def test_duplicate_reservation_is_rejected(self):
        _, service = _build()
        service.acquire("job-1", "scheduler-a")

        with pytest.raises(Error):
            service.acquire("job-1", "scheduler-b")

    def test_scheduler_isolation(self):
        _, service = _build()

        reservation_a = service.acquire("job-1", "scheduler-a")
        reservation_b = service.acquire("job-2", "scheduler-b")

        assert reservation_a.scheduler_id == "scheduler-a"
        assert reservation_b.scheduler_id == "scheduler-b"
        assert service.active("job-1").reservation_id == reservation_a.reservation_id
        assert service.active("job-2").reservation_id == reservation_b.reservation_id

    def test_only_eligible_jobs_can_be_reserved(self):
        status_service, service = _build(status_by_job={"job-1": "READY"})

        with pytest.raises(Error):
            service.acquire("job-1", "scheduler-a")

    def test_reserving_unknown_job_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.acquire("does-not-exist", "scheduler-a")

    def test_renewal(self):
        _, service = _build()
        reservation = service.acquire("job-1", "scheduler-a", ttl_seconds=1)

        renewed = service.renew(reservation.reservation_id, ttl_seconds=60)

        assert renewed.expires_at > reservation.expires_at
        assert renewed.reservation_id == reservation.reservation_id

    def test_renewing_released_reservation_is_rejected(self):
        _, service = _build()
        reservation = service.acquire("job-1", "scheduler-a")
        service.release(reservation.reservation_id)

        with pytest.raises(Error):
            service.renew(reservation.reservation_id)

    def test_expiry_frees_job_for_new_reservation(self):
        _, service = _build()
        reservation = service.acquire("job-1", "scheduler-a", ttl_seconds=-1)

        assert service.active("job-1") is None

        expired = service.expired()

        assert len(expired) == 1
        assert expired[0].reservation_id == reservation.reservation_id
        assert expired[0].status == "EXPIRED"

        new_reservation = service.acquire("job-1", "scheduler-b")

        assert new_reservation.scheduler_id == "scheduler-b"

    def test_releasing_unknown_reservation_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.release("does-not-exist")
