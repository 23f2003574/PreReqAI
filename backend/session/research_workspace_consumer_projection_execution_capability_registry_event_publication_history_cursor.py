from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor:
    """
    Immutable traversal state for a consumer projection execution
    capability registry event publication history.

    Tracks traversal state only - it does not navigate history,
    replay sessions, modify history, expose sessions, filter
    history, persist state, or log.

    Attributes:
        position: The current position within the history
        remaining_sessions: The number of sessions still ahead of
            the current position
        has_next: True when position has not yet reached the end
            of the history
    """

    position: int

    remaining_sessions: int

    has_next: bool
