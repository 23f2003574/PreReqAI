from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryWindow:
    """
    Immutable, fixed-size contiguous view of a consumer projection
    execution capability registry event subscription lifecycle
    policy evaluation history.

    A window enables deterministic batch traversal of history
    without navigating, replaying, evaluating, modifying, or
    filtering entries.

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
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry,
        ...,
    ]

    has_more: bool
