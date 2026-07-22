from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark:
    """
    Immutable, saved traversal position within a consumer projection
    execution capability registry event subscription lifecycle
    transition execution history.

    Captures navigation state only, so it can be restored later. It
    owns no navigation, reading, replay, or persistence logic.

    Attributes:
        position: The bookmarked cursor position
    """

    position: int
