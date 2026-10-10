from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_dashboard_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardSummary:
    """
    Immutable, point-in-time count of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipelines by state.

    The summary is a value object only. It performs no counting.
    Counting is the responsibility of a pipeline dashboard service,
    aggregated from the existing queue service's own statistics.

    Attributes:
        active: How many pipelines are currently running
        queued: How many pipelines are waiting to run
        completed: How many pipelines finished successfully
        failed: How many pipelines finished unsuccessfully
    """

    active: int

    queued: int

    completed: int

    failed: int

    def __post_init__(self):
        for value, label in (
            (self.active, "active"),
            (self.queued, "queued"),
            (self.completed, "completed"),
            (self.failed, "failed"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, int):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                    f"Cannot build a pipeline dashboard summary with a non-integer {label} count."
                )

            if value < 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                    f"Cannot build a pipeline dashboard summary with a negative {label} count."
                )
