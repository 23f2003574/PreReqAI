from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_reservation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationResult:
    """
    Immutable outcome of attempting to reserve a workspace resource
    for a consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session.

    The result is a value object only. It performs no reservation.
    Reserving is the responsibility of a session reservation service.

    Attributes:
        reservation_id: The identifier of the reservation this result
            concerns
        acquired: Whether the reservation succeeded
    """

    reservation_id: str

    acquired: bool

    def __post_init__(self):
        if self.reservation_id is None or not self.reservation_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation result with an empty or blank reservation ID."
            )

        if self.acquired is None or not isinstance(self.acquired, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionReservationError(
                "Cannot build a session reservation result with a non-boolean acquired."
            )
