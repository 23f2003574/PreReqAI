from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry:
    """
    Immutable representation of one completed consumer projection
    execution capability registry event subscription lifecycle
    transition execution, together with its chronological sequence
    within a lifecycle history.

    A history entry captures a single execution result and its
    sequence number. It performs no replay, execution, validation,
    persistence, sequence number generation, logging, or metrics.

    Attributes:
        sequence_number: The entry's position within its history
        execution_result: The execution result this entry records
    """

    sequence_number: int

    execution_result: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult
    )
