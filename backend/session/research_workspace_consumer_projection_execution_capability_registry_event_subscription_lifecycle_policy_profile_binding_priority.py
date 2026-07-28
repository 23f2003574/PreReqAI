from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_priority_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriority:
    """
    Immutable assignment of a selection priority to a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding.

    The priority is a value object only. It performs no selection.
    Selection is the responsibility of a binding priority service.

    Attributes:
        binding_id: The identifier of the binding this priority
            applies to
        priority: The binding's priority; higher values win when
            multiple active bindings are eligible for the same
            capability
    """

    binding_id: str

    priority: int

    def __post_init__(self):
        if self.binding_id is None or not self.binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError(
                "Cannot build a priority with an empty or blank binding ID."
            )

        if self.priority is None or self.priority < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError(
                "Cannot build a priority with a None or negative priority value."
            )
