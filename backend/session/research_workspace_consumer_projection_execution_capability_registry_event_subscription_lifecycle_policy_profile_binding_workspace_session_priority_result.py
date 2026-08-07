from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_priority_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult:
    """
    Immutable report of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace session's standing after its effective priority was
    looked up, updated, or rebalanced.

    The result is a value object only. It performs no ordering or
    aging. Computing execution order and effective priority is the
    responsibility of a session priority service.

    Attributes:
        execution_order: The session's current rank among every
            tracked session, 0 for the session that would execute
            next
        effective_priority: The session's current priority after
            aging has been applied, if enabled
    """

    execution_order: int

    effective_priority: float

    def __post_init__(self):
        if self.execution_order is None or isinstance(self.execution_order, bool) or not isinstance(self.execution_order, int):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority result with a non-integer execution_order."
            )

        if self.execution_order < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority result with a negative execution_order."
            )

        if self.effective_priority is None or isinstance(self.effective_priority, bool) or not isinstance(self.effective_priority, (int, float)):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority result with a non-numeric effective_priority."
            )
