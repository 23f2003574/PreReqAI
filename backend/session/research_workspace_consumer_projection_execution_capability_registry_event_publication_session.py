from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_publication_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession:
    """
    Immutable aggregate representing a single completed consumer
    projection execution capability registry event publication.

    Groups together the event, its publication outcome, and derived
    execution context into one read-only object. It owns no
    publication logic - it does NOT publish events, dispatch events,
    resolve subscribers, retry failures, mutate results, persist
    state, or log.

    Attributes:
        event: The event that was published
        publication_result: The publication result produced for the
            event
        subscriber_count: The number of subscribers resolved for
            the event, mirrored from publication_result
        publication_completed: True when the publication result
            reports the event as published, mirrored from
            publication_result
    """

    event: Any

    publication_result: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult

    subscriber_count: int

    publication_completed: bool
