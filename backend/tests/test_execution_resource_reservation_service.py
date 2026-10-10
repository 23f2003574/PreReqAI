import pytest

from backend.session import (
    ExecutionResourceReservation,
    ExecutionResourceReservationError as Error,
    ExecutionResourceReservationService,
)


def _build(capacity_by_resource=None):
    return ExecutionResourceReservationService(capacity_by_resource or {"gpu": 4, "memory": 16})


class TestExecutionResourceReservationService:
    def test_reserve_and_release(self):
        service = _build()

        reservation = service.reserve("job-1", "gpu", 2)

        assert isinstance(reservation, ExecutionResourceReservation)
        assert reservation.status == "ACTIVE"
        assert service.available("gpu") == 2

        released = service.release(reservation.reservation_id)

        assert released.status == "RELEASED"
        assert service.available("gpu") == 4

    def test_availability_calculation(self):
        service = _build()

        assert service.available("gpu") == 4

        service.reserve("job-1", "gpu", 1)
        service.reserve("job-2", "gpu", 2)

        assert service.available("gpu") == 1

    def test_reserve_non_positive_amount_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.reserve("job-1", "gpu", 0)

    def test_capacity_exhaustion_is_rejected(self):
        service = _build()
        service.reserve("job-1", "gpu", 4)

        with pytest.raises(Error):
            service.reserve("job-2", "gpu", 1)

    def test_duplicate_active_reservation_for_same_job_and_resource_is_rejected(self):
        service = _build()
        service.reserve("job-1", "gpu", 1)

        with pytest.raises(Error):
            service.reserve("job-1", "gpu", 1)

    def test_reserving_unknown_resource_type_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.reserve("job-1", "disk", 1)

    def test_expiry_releases_capacity(self):
        service = _build()
        reservation = service.reserve("job-1", "gpu", 2, ttl_seconds=-1)

        assert service.available("gpu") == 4

        expired = service.expire()

        assert len(expired) == 1
        assert expired[0].reservation_id == reservation.reservation_id
        assert expired[0].status == "EXPIRED"

    def test_expired_reservation_frees_job_for_a_new_reservation(self):
        service = _build()
        service.reserve("job-1", "gpu", 2, ttl_seconds=-1)

        reservation = service.reserve("job-1", "gpu", 1)

        assert reservation.status == "ACTIVE"

    def test_active_only_reports_currently_active_reservations(self):
        service = _build()
        service.reserve("job-1", "gpu", 1, ttl_seconds=-1)
        gpu_reservation = service.reserve("job-1", "memory", 1)

        active = service.active("job-1")

        assert len(active) == 1
        assert active[0].reservation_id == gpu_reservation.reservation_id

    def test_resource_isolation(self):
        service = _build()
        service.reserve("job-1", "gpu", 4)

        assert service.available("gpu") == 0
        assert service.available("memory") == 16

    def test_releasing_unknown_reservation_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.release("does-not-exist")

    def test_releasing_already_released_reservation_is_rejected(self):
        service = _build()
        reservation = service.reserve("job-1", "gpu", 1)
        service.release(reservation.reservation_id)

        with pytest.raises(Error):
            service.release(reservation.reservation_id)
