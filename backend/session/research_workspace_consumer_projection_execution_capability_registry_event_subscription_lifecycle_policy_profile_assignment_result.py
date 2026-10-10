from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult:
    """
    Immutable outcome produced after assigning or unassigning a
    consumer projection execution capability registry event
    subscription lifecycle policy profile to or from a target.

    The result is a value object only. It performs no assignment
    logic. Assignment and unassignment are the responsibility of an
    assignment service.

    Attributes:
        assignment: The assignment record produced by the operation
        successful: Whether the operation completed without error
    """

    assignment: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment
    )

    successful: bool
