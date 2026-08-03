from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult:
    """
    Immutable result of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branch action.

    Attributes:
        branch: The branch the action produced or acted on
        successful: True if the action actually changed branch state;
            False if it was a redundant no-op, such as checking out a
            branch that was already active
    """

    branch: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch

    successful: bool
