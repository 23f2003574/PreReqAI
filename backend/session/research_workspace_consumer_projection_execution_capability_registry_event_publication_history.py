from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory:
    """
    Immutable, chronological collection of completed consumer
    projection execution capability registry event publication
    sessions.

    Captures state only - it does not publish events, replay
    history, query sessions, or persist data.

    Attributes:
        sessions: The publication sessions, in chronological order
        session_count: The number of sessions in the history
    """

    sessions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
        ...,
    ]

    session_count: int
