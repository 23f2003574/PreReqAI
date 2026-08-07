import time

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation as Reservation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus as Status,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationService as ReservationService,
)


class TestWorkspaceSessionScheduleReservationService:
    def test_reserve_slot(self):
        service = ReservationService(slot_ids=("slot-1", "slot-2"))

        reservation = service.reserve("schedule-1")

        assert isinstance(reservation, Reservation)
        assert reservation.schedule_id == "schedule-1"
        assert reservation.slot_id in ("slot-1", "slot-2")

    def test_duplicate_reservation_rejection(self):
        service = ReservationService(slot_ids=("slot-1",))

        service.reserve("schedule-1")

        with pytest.raises(Error):
            service.reserve("schedule-2")

    def test_release_reservation(self):
        service = ReservationService(slot_ids=("slot-1",))
        reservation = service.reserve("schedule-1")

        status = service.release(reservation.reservation_id)

        assert isinstance(status, Status)
        assert status.reserved is False
        assert status.expires_at is None

        with pytest.raises(Error):
            service.release(reservation.reservation_id)

    def test_reservation_owner_lookup(self):
        service = ReservationService(slot_ids=("slot-1",))

        status = service.owner("slot-1")
        assert status.reserved is False
        assert status.expires_at is None

        reservation = service.reserve("schedule-1")

        status = service.owner("slot-1")
        assert status.reserved is True
        assert status.expires_at == reservation.reserved_until

        with pytest.raises(Error):
            service.owner("unknown-slot")

    def test_expiration_cleanup(self):
        service = ReservationService(slot_ids=("slot-1",), reservation_duration_seconds=0.05)
        reservation = service.reserve("schedule-1")

        time.sleep(0.1)

        assert service.owner("slot-1").reserved is False

        stale = service.expired()
        assert [entry.reservation_id for entry in stale] == [reservation.reservation_id]

        removed = service.cleanup()
        assert [entry.reservation_id for entry in removed] == [reservation.reservation_id]
        assert service.expired() == ()

        with pytest.raises(Error):
            service.release(reservation.reservation_id)

    def test_slot_reuse_after_release(self):
        service = ReservationService(slot_ids=("slot-1",))

        first = service.reserve("schedule-1")
        service.release(first.reservation_id)

        # freed immediately: a different schedule can now reserve it
        second = service.reserve("schedule-2")
        assert second.slot_id == "slot-1"
        assert service.owner("slot-1").reserved is True
