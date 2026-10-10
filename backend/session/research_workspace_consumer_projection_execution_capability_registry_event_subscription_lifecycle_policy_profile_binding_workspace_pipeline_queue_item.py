from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_item_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItem:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline waiting for, or currently
    undergoing, managed execution.

    The item is a value object only. It performs no scheduling and no
    execution. Scheduling and execution are the responsibility of a
    pipeline queue service.

    Attributes:
        queue_item_id: The item's unique identifier
        pipeline_id: The identifier of the pipeline the item concerns
        priority: The item's scheduling priority; a higher value is
            scheduled before a lower one, and must be a non-negative
            integer
        queued_at: When the item was enqueued; used to break ties
            between items sharing the same priority, in FIFO order
        status: The item's current state
    """

    queue_item_id: str

    pipeline_id: str

    priority: int

    queued_at: datetime

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus = field(
        default=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.QUEUED
    )

    def __post_init__(self):
        if self.queue_item_id is None or not self.queue_item_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                "Cannot build a pipeline queue item with an empty or blank queue item ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                "Cannot build a pipeline queue item with an empty or blank pipeline ID."
            )

        if self.priority is None or isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                "Cannot build a pipeline queue item with a non-integer priority."
            )

        if self.priority < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                f"Cannot build a pipeline queue item with priority {self.priority!r}; priority must not be "
                "negative."
            )

        if self.queued_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                "Cannot build a pipeline queue item with a None queued_at."
            )

        if not isinstance(self.status, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                "Cannot build a pipeline queue item: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus."
            )
