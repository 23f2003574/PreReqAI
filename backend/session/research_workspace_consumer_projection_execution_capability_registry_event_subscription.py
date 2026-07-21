from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscriber import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription:
    """
    Immutable representation of a subscriber's registration within
    the consumer projection execution capability registry.

    A subscription captures the relationship between a subscriber
    and the registry. It performs no registration, dispatch,
    publication, or lifecycle management.

    Attributes:
        subscriber: The registered subscriber
        subscription_id: The identifier assigned to this
            registration
        active: Whether the subscription is currently active
    """

    subscriber: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
    )

    subscription_id: str

    active: bool
