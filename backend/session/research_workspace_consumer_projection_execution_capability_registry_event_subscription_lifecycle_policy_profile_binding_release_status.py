from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus(
    str,
    Enum,
):
    """
    Canonical states a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    version may occupy in its release lifecycle.

    This enum only names the possible statuses. It performs no
    transition logic. A (binding, version) pair implicitly starts in
    DRAFT until a release service records its first release.
    """

    DRAFT = "draft"

    RELEASED = "released"

    RETIRED = "retired"
