from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpoint:
    """
    Immutable synchronization state of a consumer projection
    execution capability registry event publication history
    traversal.

    Unlike a bookmark, which is used to restore navigation, a
    checkpoint represents progress through the history for use by
    higher-level synchronization workflows. It performs no
    navigation, replay, or persistence.

    Attributes:
        session_count: The history's session count at the time the
            checkpoint was built
        last_position: The cursor position the checkpoint was built
            from
        is_empty: True when the history has no sessions
    """

    session_count: int

    last_position: int

    is_empty: bool
