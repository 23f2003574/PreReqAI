from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult:
    """
    Immutable record of one completed consumer projection execution
    capability registry event subscription lifecycle transition.

    The execution result captures the input lifecycle, the executed
    transition, and the resulting lifecycle. It performs no
    execution, validation, mutation, persistence, or logging of its
    own.

    Attributes:
        previous_lifecycle: The lifecycle before the transition was
            applied
        transition: The transition that was executed
        resulting_lifecycle: The lifecycle after the transition was
            applied
    """

    previous_lifecycle: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle
    )

    transition: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition
    )

    resulting_lifecycle: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle
    )
