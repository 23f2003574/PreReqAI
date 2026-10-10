from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus(
    str,
    Enum,
):
    """
    Canonical states a consumer projection execution capability
    registry event subscription lifecycle policy template version
    may occupy in its release lifecycle.

    This enum only names the possible statuses. It performs no
    transition logic. A version implicitly starts in DRAFT until a
    release service records its first release.
    """

    DRAFT = (
        "draft"
    )

    RELEASED = (
        "released"
    )

    RETIRED = (
        "retired"
    )
