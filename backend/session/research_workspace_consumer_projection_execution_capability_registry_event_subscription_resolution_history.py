from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory:
    """
    Immutable, chronological collection of completed consumer
    projection execution capability registry event subscription
    resolution sessions.

    Captures state only - it does not resolve subscriptions,
    dispatch events, replay history, query sessions, or persist
    data.

    Attributes:
        sessions: The resolution sessions, in chronological order
        session_count: The number of sessions in the history
    """

    sessions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
        ...,
    ]

    session_count: int
