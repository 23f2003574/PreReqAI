from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus(
    str,
    Enum,
):
    """
    Canonical states a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace pipeline gate can occupy.

    This enum only names the possible states. It performs no
    transition logic.
    """

    PENDING = "pending"

    OPEN = "open"

    CLOSED = "closed"

    BYPASSED = "bypassed"
