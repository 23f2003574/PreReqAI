from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_balancer_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment:
    """
    Immutable record of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session having been placed on a single
    execution worker.

    The assignment is a value object only. It performs no placement.
    Assigning and rebalancing sessions across workers is the
    responsibility of a session scheduling balancer service.

    Attributes:
        session_id: The identifier of the execution session this
            assignment concerns
        worker_id: The identifier of the execution worker the session
            was placed on
        assigned_at: When this assignment was made
    """

    session_id: str

    worker_id: str

    assigned_at: datetime

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling assignment with an empty or blank session ID."
            )

        if self.worker_id is None or not self.worker_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling assignment with an empty or blank worker ID."
            )

        if self.assigned_at is None or not isinstance(self.assigned_at, datetime) or self.assigned_at.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling assignment with a non-timezone-aware assigned_at."
            )
