from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_quota_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult:
    """
    Immutable outcome produced after reserving or validating a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace pipeline
    resource budget against the remaining quota pool.

    The result is a value object only. It performs no reservation.
    Reservation is the responsibility of a pipeline quota service.

    Attributes:
        accepted: Whether the budget was reserved, or would fit,
            within the remaining quota pool
        reason: Why the budget was accepted or rejected
        remaining_budget: The quota pool's remaining max_runtime,
            max_memory, and max_parallel_tasks after this outcome
    """

    accepted: bool

    reason: str

    remaining_budget: Mapping

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline quota result with a non-boolean accepted flag."
            )

        if self.reason is None or not self.reason.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline quota result with an empty or blank reason."
            )

        if self.remaining_budget is None or not isinstance(self.remaining_budget, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline quota result with remaining_budget that is not a mapping."
            )
