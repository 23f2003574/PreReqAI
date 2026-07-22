from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition:
    """
    Immutable representation of a consumer projection execution
    capability registry event subscription's movement between two
    lifecycle states.

    A transition describes movement between states. It performs no
    validation of legal transition paths, no execution of state
    changes, and no mutation of the subscription.

    Attributes:
        subscription: The subscription this transition describes
        from_state: The lifecycle state being moved from
        to_state: The lifecycle state being moved to
    """

    subscription: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription
    )

    from_state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState
    )

    to_state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState
    )
