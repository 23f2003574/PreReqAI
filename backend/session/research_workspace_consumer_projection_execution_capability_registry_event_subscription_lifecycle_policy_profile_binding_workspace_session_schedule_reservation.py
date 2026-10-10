from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_reservation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservation:
    """
    Immutable, time-boxed claim a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule holds on a single execution
    slot, so a competing schedule cannot claim the same execution
    window at the same time.

    The reservation is a value object only. It performs no expiry
    enforcement. Reserving, releasing, and cleaning up reservations is
    the responsibility of a session schedule reservation service.

    Attributes:
        reservation_id: The reservation's unique identifier
        schedule_id: The identifier of the schedule holding this
            reservation
        slot_id: The identifier of the execution slot this
            reservation claims
        reserved_until: When this reservation lapses if not released
            first
    """

    reservation_id: str

    schedule_id: str

    slot_id: str

    reserved_until: datetime

    def __post_init__(self):
        if self.reservation_id is None or not self.reservation_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session schedule reservation with an empty or blank reservation ID."
            )

        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session schedule reservation with an empty or blank schedule ID."
            )

        if self.slot_id is None or not self.slot_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session schedule reservation with an empty or blank slot ID."
            )

        if self.reserved_until is None or not isinstance(self.reserved_until, datetime) or self.reserved_until.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session schedule reservation with a non-timezone-aware reserved_until."
            )
