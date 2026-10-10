from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry:
    """
    Immutable representation of one completed consumer projection
    execution capability registry event subscription lifecycle
    policy evaluation, together with its chronological sequence
    within a policy evaluation history.

    A history entry captures a single evaluation result and its
    sequence number. It performs no evaluation, replay, validation,
    persistence, sequence number generation, logging, or metrics.

    Attributes:
        sequence_number: The entry's position within its history
        evaluation_result: The evaluation result this entry records
    """

    sequence_number: int

    evaluation_result: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult
    )
