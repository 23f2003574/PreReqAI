from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_reservation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationStatus:
    """
    Immutable, point-in-time report of whether a single execution
    slot is currently held by a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule reservation.

    The status is a value object only. It performs no lookup.
    Reporting a slot's or a reservation's current status is the
    responsibility of a session schedule reservation service.

    Attributes:
        reserved: Whether the slot this status concerns is currently
            held by an active reservation
        expires_at: When the active reservation lapses, or None when
            reserved is False
    """

    reserved: bool

    expires_at: Optional[datetime]

    def __post_init__(self):
        if self.reserved is None or not isinstance(self.reserved, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session reservation status with a non-boolean reserved."
            )

        if self.expires_at is not None and not isinstance(self.expires_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a session reservation status with a non-datetime expires_at."
            )

        if self.reserved and self.expires_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build a reserved session reservation status without an expires_at."
            )

        if not self.reserved and self.expires_at is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleReservationError(
                "Cannot build an unreserved session reservation status with an expires_at."
            )
