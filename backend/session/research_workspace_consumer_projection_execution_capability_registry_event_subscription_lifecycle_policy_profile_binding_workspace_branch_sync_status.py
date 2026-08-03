from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus(
    str,
    Enum,
):
    """
    Canonical outcomes a single attempt to synchronize a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace branch with its
    workspace's latest revision can have.

    This enum only names the possible outcomes. It performs no
    synchronization logic; a workspace branch synchronization service
    is responsible for determining which outcome an attempt produced.
    """

    SUCCEEDED = "succeeded"

    FAILED = "failed"
