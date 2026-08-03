from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus(
    str,
    Enum,
):
    """
    Canonical outcomes a single attempt to rebase a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace change set onto a
    newer workspace revision can have.

    This enum only names the possible outcomes. It performs no
    rebasing logic; a workspace rebase service is responsible for
    determining which outcome an attempt produced.
    """

    SUCCEEDED = "succeeded"

    FAILED = "failed"
