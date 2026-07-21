from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow:
    """
    Immutable, fixed-size contiguous view of a consumer projection
    execution capability registry event subscription resolution
    history.

    A window enables deterministic batch traversal of history
    without replaying, modifying, or filtering sessions.

    Attributes:
        start_position: The position the window begins at
        window_size: The requested window size
        sessions: The sessions within the window, in chronological
            order
        has_more: True when sessions remain beyond the end of this
            window
    """

    start_position: int

    window_size: int

    sessions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
        ...,
    ]

    has_more: bool
