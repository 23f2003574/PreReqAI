from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindow:
    """
    Immutable, fixed-size contiguous view of a consumer projection
    execution capability registry event subscription lifecycle
    transition execution history.

    A window enables deterministic batch traversal of history
    without navigating, replaying, modifying, or filtering entries.

    Attributes:
        start_position: The position the window begins at
        window_size: The requested window size
        entries: The entries within the window, in chronological
            order
        has_more: True when entries remain beyond the end of this
            window
    """

    start_position: int

    window_size: int

    entries: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
        ...,
    ]

    has_more: bool
