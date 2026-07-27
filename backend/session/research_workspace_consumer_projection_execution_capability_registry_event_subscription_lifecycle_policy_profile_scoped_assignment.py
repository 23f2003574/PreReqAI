from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_scope import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_scope_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileScopedAssignment:
    """
    Immutable record of a profile assigned to a target under a specific scope context.

    Attributes:
        target_id: The identifier of the target capability or subscription.
        profile_id: The identifier of the assigned profile.
        scope: The scope instance applying to this assignment.
    """

    target_id: str

    profile_id: str

    scope: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope

    def __post_init__(self):
        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot build a scoped assignment with an empty or blank target ID."
            )

        if self.profile_id is None or not self.profile_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot build a scoped assignment with an empty or blank profile ID."
            )

        if self.scope is None or not isinstance(
            self.scope,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot build a scoped assignment with an invalid or None scope."
            )
