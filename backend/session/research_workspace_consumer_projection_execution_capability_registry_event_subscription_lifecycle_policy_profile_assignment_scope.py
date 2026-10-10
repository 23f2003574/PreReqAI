from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_scope_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope:
    """
    Immutable description of a scope (e.g. environment, tenant, or namespace)
    context for profile assignments.

    Attributes:
        scope_id: The unique identifier of the scope instance.
        scope_type: The type of scope (e.g. "environment", "tenant").
        scope_value: The value of the scope (e.g. "production", "123").
    """

    scope_id: str

    scope_type: str

    scope_value: str

    def __post_init__(self):
        if self.scope_id is None or not self.scope_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot build a scope with an empty or blank scope ID."
            )

        if self.scope_type is None or not self.scope_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot build a scope with an empty or blank scope type."
            )

        if self.scope_value is None or not self.scope_value.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot build a scope with an empty or blank scope value."
            )
