from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityResult:
    """
    Immutable outcome produced after resolving the highest-priority
    active consumer projection execution capability registry event
    subscription lifecycle policy profile binding for a capability.

    Attributes:
        selected_binding: The binding selected as highest priority,
            or None if no active binding was eligible
        evaluated_bindings: An immutable tuple of every active binding
            that was considered, ordered from highest to lowest
            priority
    """

    selected_binding: object

    evaluated_bindings: tuple
