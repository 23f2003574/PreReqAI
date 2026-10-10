from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_reservation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservation:
    """
    Immutable claim on a single logical workspace resource, held by
    one consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session, so no conflicting session can claim the same resource
    while it holds it.

    The reservation is a value object only. It performs no
    exclusivity enforcement or expiry. Reserving, releasing, and
    expiring reservations are the responsibility of a session
    reservation service.

    Attributes:
        reservation_id: The reservation's unique identifier
        session_id: The identifier of the execution session holding
            this reservation
        resource_type: The kind of resource reserved
        resource_id: The identifier of the specific resource reserved,
            unique within resource_type
        expires_at: When this reservation lapses if not released first
    """

    reservation_id: str

    session_id: str

    resource_type: str

    resource_id: str

    expires_at: datetime

    def __post_init__(self):
        if self.reservation_id is None or not self.reservation_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation with an empty or blank reservation ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation with an empty or blank session ID."
            )

        if self.resource_type is None or not self.resource_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation with an empty or blank resource type."
            )

        if self.resource_id is None or not self.resource_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation with an empty or blank resource ID."
            )

        if self.expires_at is None or not isinstance(self.expires_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation with a non-datetime expires_at."
            )
