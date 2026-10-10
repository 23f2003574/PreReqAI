from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus(
    str,
    Enum,
):
    """
    Canonical states a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace pipeline queue item can occupy.

    This enum only names the possible states. It performs no
    transition logic.
    """

    QUEUED = "queued"

    RUNNING = "running"

    COMPLETED = "completed"

    FAILED = "failed"
