from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus(
    str,
    Enum,
):
    """
    Canonical lifecycle states a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline can occupy.

    This enum only names the possible states. It performs no
    transition logic.
    """

    CREATED = "created"

    RUNNING = "running"

    PAUSED = "paused"

    COMPLETED = "completed"

    FAILED = "failed"

    CANCELLED = "cancelled"
