from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_quota_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget:
    """
    Immutable resource request a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline must be granted before it
    may start, so no single pipeline can starve the others of
    runtime, memory, or parallelism.

    The budget is a value object only. It performs no reservation, no
    tracking, and no enforcement. Reservation, tracking, and
    enforcement are the responsibility of a pipeline quota service.

    Attributes:
        budget_id: The budget's unique identifier
        pipeline_id: The identifier of the pipeline the budget
            belongs to
        max_runtime: The maximum runtime, in seconds, the pipeline
            may consume; must not be negative
        max_memory: The maximum memory, in megabytes, the pipeline
            may consume; must not be negative
        max_parallel_tasks: The maximum number of tasks the pipeline
            may run in parallel; must not be negative
    """

    budget_id: str

    pipeline_id: str

    max_runtime: float

    max_memory: float

    max_parallel_tasks: int

    def __post_init__(self):
        if self.budget_id is None or not self.budget_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline resource budget with an empty or blank budget ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline resource budget with an empty or blank pipeline ID."
            )

        if (
            self.max_runtime is None
            or isinstance(self.max_runtime, bool)
            or not isinstance(self.max_runtime, (int, float))
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline resource budget with a non-numeric max_runtime."
            )

        if self.max_runtime < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                f"Cannot build a pipeline resource budget with a negative max_runtime {self.max_runtime!r}."
            )

        if (
            self.max_memory is None
            or isinstance(self.max_memory, bool)
            or not isinstance(self.max_memory, (int, float))
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline resource budget with a non-numeric max_memory."
            )

        if self.max_memory < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                f"Cannot build a pipeline resource budget with a negative max_memory {self.max_memory!r}."
            )

        if (
            self.max_parallel_tasks is None
            or isinstance(self.max_parallel_tasks, bool)
            or not isinstance(self.max_parallel_tasks, int)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline resource budget with a non-integer max_parallel_tasks."
            )

        if self.max_parallel_tasks < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot build a pipeline resource budget with a negative max_parallel_tasks "
                f"{self.max_parallel_tasks!r}."
            )
