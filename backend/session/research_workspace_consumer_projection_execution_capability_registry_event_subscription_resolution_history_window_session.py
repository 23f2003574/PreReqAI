from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_window import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSession:
    """
    Immutable aggregate representing an active traversal session
    over consumer projection execution capability registry event
    subscription resolution history windows.

    Groups together the history, the current window, and traversal
    state into one read-only object. It owns no navigation, replay,
    or processing logic - it does NOT navigate history, replay
    sessions, modify history, filter windows, persist sessions,
    process resolution sessions, or log.

    Attributes:
        history: The resolution history being traversed
        current_window: The active window within the history
        window_size: The window size the session was built with
        has_remaining_windows: True when the current window reports
            more sessions beyond it, mirrored from
            current_window.has_more
    """

    history: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistory

    current_window: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindow

    window_size: int

    has_remaining_windows: bool
