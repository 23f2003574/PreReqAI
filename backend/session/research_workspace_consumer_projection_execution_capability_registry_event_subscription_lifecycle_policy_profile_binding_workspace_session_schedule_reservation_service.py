from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_reservation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_reservation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_reservation_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationService:
    """
    Reserves execution slots on behalf of consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace session schedules, so two competing
    schedules can never claim the same execution window at the same
    time.

    The service manages a fixed pool of execution slots, given at
    construction time. Its responsibility is slot exclusivity and
    expiry, not execution itself. It does NOT dispatch a schedule for
    execution; a caller, such as the session scheduler, is expected to
    call reserve() before dispatching a schedule and release() once
    that schedule's execution finishes.

    Behavior:
    - At most one active reservation may exist per slot at a time;
      reserve() claims the first free slot, in pool order, and fails
      if every slot is currently held
    - A reservation past its reserved_until is treated as no longer
      active: owner() disregards it, and expired() and cleanup() both
      report it as stale
    - release() frees a reservation's slot immediately
    - expired() only reports stale reservations still held in storage;
      cleanup() additionally removes them, freeing their slots

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, slot_ids: tuple, reservation_duration_seconds: float = 60.0):
        """
        Args:
            slot_ids: The fixed pool of execution slot identifiers
                this service manages
            reservation_duration_seconds: How long, in seconds, a
                reservation remains active after being reserved

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError:
                If slot_ids is not a non-empty tuple of unique,
                non-blank strings, or reservation_duration_seconds is
                not a positive number
        """

        if (
            not isinstance(slot_ids, tuple)
            or not slot_ids
            or any(slot_id is None or not isinstance(slot_id, str) or not slot_id.strip() for slot_id in slot_ids)
            or len(set(slot_ids)) != len(slot_ids)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session schedule reservation service with slot_ids that is not a non-empty tuple "
                "of unique, non-blank strings."
            )

        if (
            reservation_duration_seconds is None
            or isinstance(reservation_duration_seconds, bool)
            or not isinstance(reservation_duration_seconds, (int, float))
            or reservation_duration_seconds <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session schedule reservation service with a non-positive "
                "reservation_duration_seconds."
            )

        self._slot_ids = slot_ids
        self._reservation_duration = timedelta(seconds=reservation_duration_seconds)
        self._reservations = {}
        self._active_reservation_id_by_slot_id = {}
        self._lock = RLock()

    def reserve(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation:
        """
        Reserve the first free execution slot, in pool order, on
        behalf of a schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError:
                If schedule_id is None or blank, or every execution
                slot is currently held by an active reservation
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            free_slot_id = self._first_free_slot()

            if free_slot_id is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                    "Cannot reserve an execution slot: every slot is currently held by an active reservation."
                )

            reservation = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation(
                reservation_id=str(uuid4()),
                schedule_id=schedule_id,
                slot_id=free_slot_id,
                reserved_until=datetime.now(timezone.utc) + self._reservation_duration,
            )

            self._reservations[reservation.reservation_id] = reservation
            self._active_reservation_id_by_slot_id[free_slot_id] = reservation.reservation_id

            return reservation

    def release(self, reservation_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus:
        """
        Release a reservation, freeing its slot immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError:
                If reservation_id is None or blank, or no reservation
                is registered under it
        """

        self._validate_id(reservation_id, "reservation ID")

        with self._lock:
            self._resolve(reservation_id)

            self._forget(reservation_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus(
                reserved=False,
                expires_at=None,
            )

    def owner(self, slot_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus:
        """
        Check whether an execution slot is currently held.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError:
                If slot_id is None or blank, or it is not part of this
                service's slot pool
            """

        self._validate_id(slot_id, "slot ID")

        if slot_id not in self._slot_ids:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                f"Slot ID {slot_id!r} is not part of this service's execution slot pool."
            )

        with self._lock:
            reservation = self._active_reservation_for_slot(slot_id)

            if reservation is None:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus(
                    reserved=False,
                    expires_at=None,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus(
                reserved=True,
                expires_at=reservation.reserved_until,
            )

    def expired(self) -> tuple:
        """
        List every reservation past its reserved_until, still held in
        storage.
        """

        with self._lock:
            return tuple(reservation for reservation in self._reservations.values() if not self._is_active(reservation))

    def cleanup(self) -> tuple:
        """
        Remove every reservation past its reserved_until from
        storage, freeing its slot.

        Returns:
            The reservations that were removed
        """

        with self._lock:
            stale = self.expired()

            for reservation in stale:
                self._forget(reservation.reservation_id)

            return stale

    def _first_free_slot(self):
        for slot_id in self._slot_ids:
            if self._active_reservation_for_slot(slot_id) is None:
                return slot_id

        return None

    def _active_reservation_for_slot(self, slot_id: str):
        reservation_id = self._active_reservation_id_by_slot_id.get(slot_id)

        if reservation_id is None:
            return None

        reservation = self._reservations[reservation_id]

        if not self._is_active(reservation):
            return None

        return reservation

    def _is_active(self, reservation: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation) -> bool:
        return reservation.reserved_until > datetime.now(timezone.utc)

    def _forget(self, reservation_id: str) -> None:
        reservation = self._reservations.pop(reservation_id, None)

        if reservation is None:
            return

        if self._active_reservation_id_by_slot_id.get(reservation.slot_id) == reservation_id:
            del self._active_reservation_id_by_slot_id[reservation.slot_id]

    def _resolve(self, reservation_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation:
        reservation = self._reservations.get(reservation_id)

        if reservation is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                f"No session schedule reservation is registered under reservation ID {reservation_id!r}."
            )

        return reservation

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                f"Cannot operate with an empty or blank {label}."
            )
