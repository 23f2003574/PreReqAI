from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_cursor import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursor,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_history_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReadResult:
    """
    Immutable outcome of a single read against a consumer projection
    execution capability registry event subscription lifecycle
    policy evaluation history.

    Captures state only - it does not navigate history, mutate
    history, replay evaluations, filter entries, persist state, or
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

    cursor: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursor

    entry: Optional[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry
    ]

    entry_found: bool
