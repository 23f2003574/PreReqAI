from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_resolution_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReadResult:
    """
    Immutable outcome of a single read against a consumer projection
    execution capability registry event subscription resolution
    history.

    Captures state only - it does not navigate history, mutate
    history, replay sessions, filter sessions, persist state, or
    log.

    Attributes:
        session: The resolution session at the cursor's position,
            or None when the cursor has already reached the end of
            the history
        cursor: The same cursor the read was performed with - the
            reader never advances traversal
        reached_end: True when the cursor had no next session to
            read
    """

    session: Optional[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSession
    ]

    cursor: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursor

    reached_end: bool
