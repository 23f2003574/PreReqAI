from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueStatistics:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace pipeline queue's item counts by state.

    The snapshot is a value object only. It performs no counting.
    Counting is the responsibility of a pipeline queue service.

    Attributes:
        queued: How many items are waiting to run
        running: How many items are currently running
        completed: How many items finished successfully
        failed: How many items finished unsuccessfully
    """

    queued: int

    running: int

    completed: int

    failed: int

    def __post_init__(self):
        for value, label in (
            (self.queued, "queued"),
            (self.running, "running"),
            (self.completed, "completed"),
            (self.failed, "failed"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, int):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                    f"Cannot build a pipeline queue statistics snapshot with a non-integer {label} count."
                )

            if value < 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                    f"Cannot build a pipeline queue statistics snapshot with a negative {label} count."
                )
