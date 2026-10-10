from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_dispatch_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult:
    """
    Immutable outcome of a completed consumer projection execution
    capability registry event publication.

    Unlike a dispatch result, which represents delivery to a
    resolved subscriber set, a publication result represents the
    overall publication process initiated by the publisher. It does
    NOT publish events, dispatch events, retry delivery, store
    subscribers, mutate state, log, or persist anything.

    Attributes:
        event: The event that was published
        resolved_subscriber_count: The number of subscribers
            resolved for the event
        dispatch_result: The dispatch result produced for the event
        published: True when the dispatch result reports completion
    """

    event: Any

    resolved_subscriber_count: int

    dispatch_result: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult

    published: bool
