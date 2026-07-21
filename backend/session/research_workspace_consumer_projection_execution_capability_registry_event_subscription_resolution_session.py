from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession:
    """
    Immutable aggregate representing a single completed consumer
    projection execution capability registry event subscription
    resolution.

    Groups together the event and its subscription resolution
    outcome into one read-only object. It owns no resolution or
    publication logic - it does NOT resolve subscriptions, dispatch
    events, publish events, mutate subscriptions, retry operations,
    persist state, or log.

    Attributes:
        event: The event resolution was performed for
        resolution: The subscription resolution produced for the
            event
        resolved_subscription_count: The number of subscriptions
            resolved for the event, mirrored from resolution
        resolution_completed: True once the session has been built
            from a completed resolution
    """

    event: Any

    resolution: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolution

    resolved_subscription_count: int

    resolution_completed: bool
