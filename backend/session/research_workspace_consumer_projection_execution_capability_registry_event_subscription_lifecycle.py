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
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle:
    """
    Immutable representation of a consumer projection execution
    capability registry event subscription's current lifecycle
    state.

    The lifecycle captures a subscription's state at a point in
    time. It performs no activation, suspension, unregistration,
    dispatch, publication, or mutation of the subscription.

    Attributes:
        subscription: The subscription this lifecycle describes
        state: The subscription's current lifecycle state
    """

    subscription: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription
    )

    state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState
    )
