from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus(
    str,
    Enum,
):
    """
    Canonical outcomes a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    deployment record can carry.

    This enum only names the possible outcomes. It performs no
    recording or querying logic.
    """

    SUCCEEDED = "succeeded"

    FAILED = "failed"
