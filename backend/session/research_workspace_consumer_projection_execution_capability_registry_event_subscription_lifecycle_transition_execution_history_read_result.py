from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReadResult:
    """
    Immutable outcome of a single read against a consumer projection
    execution capability registry event subscription lifecycle
    transition execution history.

    Captures state only - it does not navigate history, mutate
    history, replay transitions, filter entries, persist state, or
    log.

    Attributes:
        cursor: The same cursor the read was performed with - the
            reader never advances traversal
        entry: The history entry at the cursor's position, or None
            when the cursor has already reached the end of the
            history
        entry_found: True when an entry was found at the cursor's
            position
    """

    cursor: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor

    entry: Optional[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry
    ]

    entry_found: bool
