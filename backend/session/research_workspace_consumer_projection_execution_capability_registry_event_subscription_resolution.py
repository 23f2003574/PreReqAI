from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution:
    """
    Immutable outcome of resolving the subscriptions selected for
    publication of a consumer projection execution capability
    registry event.

    A resolution captures the set of subscriptions selected for
    publication. It performs no dispatching, registration, or
    filtering.

    Attributes:
        event: The event resolution was performed for
        subscriptions: The resolved subscriptions, in resolution
            order
        resolved_subscription_count: The number of resolved
            subscriptions
    """

    event: object

    subscriptions: tuple

    resolved_subscription_count: int
