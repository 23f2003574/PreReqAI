from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus(
    str,
    Enum,
):
    """
    Canonical stages a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace version's controlled release lifecycle can occupy.

    This enum only names the possible stages. It performs no
    transition validation or execution. Only a version currently
    holding RELEASED status is deployable.
    """

    DRAFT = "draft"

    RELEASED = "released"

    RETIRED = "retired"
