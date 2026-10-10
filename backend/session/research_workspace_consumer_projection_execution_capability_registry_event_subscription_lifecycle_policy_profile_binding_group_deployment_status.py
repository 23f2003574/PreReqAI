from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus(
    str,
    Enum,
):
    """
    Canonical outcomes a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    group deployment record can carry.

    This enum only names the possible outcomes. It performs no
    recording or querying logic.
    """

    SUCCEEDED = "succeeded"

    FAILED = "failed"
