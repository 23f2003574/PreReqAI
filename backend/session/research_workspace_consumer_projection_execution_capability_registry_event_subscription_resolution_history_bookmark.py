from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBookmark:
    """
    Immutable, saved traversal position within a consumer projection
    execution capability registry event subscription resolution
    history.

    Captures navigation state only, so it can be restored later. It
    owns no navigation, reading, or replay logic.

    Attributes:
        position: The bookmarked cursor position
        session_count: The history's session count at the time the
            bookmark was created
    """

    position: int

    session_count: int
