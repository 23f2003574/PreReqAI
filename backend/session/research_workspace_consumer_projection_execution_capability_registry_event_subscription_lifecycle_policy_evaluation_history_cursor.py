from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursor:
    """
    Immutable traversal state for a consumer projection execution
    capability registry event subscription lifecycle policy
    evaluation history.

    Tracks traversal state only - it does not navigate history,
    replay evaluations, modify history, expose entries, filter
    history, persist state, or log.

    Attributes:
        position: The current position within the history
        remaining_entries: The number of entries still ahead of the
            current position
        has_next: True when position has not yet reached the end
            of the history
    """

    position: int

    remaining_entries: int

    has_next: bool
