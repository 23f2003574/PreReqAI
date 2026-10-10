from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy:
    """
    Immutable configuration describing which lifecycle states are
    permitted for a consumer projection execution capability
    registry event subscription, and which state a subscription
    starts in.

    The policy is a configuration object only. It performs no
    validation of transitions, execution of transitions, activation,
    suspension, unregistration, persistence, logging, or publication.

    Attributes:
        allowed_states: The lifecycle states permitted under this
            policy
        initial_state: The lifecycle state a subscription starts in
    """

    allowed_states: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
        ...,
    ]

    initial_state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState
    )
