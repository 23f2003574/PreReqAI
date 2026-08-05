from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_ownership_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner:
    """
    Immutable record of a single worker or coordinator holding
    ownership of a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session, at a specific point in that session's
    ownership history.

    The owner record is a value object only. It performs no
    assignment or transfer. Assigning, transferring, and releasing
    ownership are the responsibility of a session ownership service.

    Attributes:
        session_id: The identifier of the execution session this
            record concerns
        owner_id: The identifier of the worker or coordinator holding
            ownership
        assigned_at: When this ownership began
    """

    session_id: str

    owner_id: str

    assigned_at: datetime

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session owner record with an empty or blank session ID."
            )

        if self.owner_id is None or not self.owner_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session owner record with an empty or blank owner ID."
            )

        if self.assigned_at is None or not isinstance(self.assigned_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                "Cannot build a session owner record with a non-datetime assigned_at."
            )
