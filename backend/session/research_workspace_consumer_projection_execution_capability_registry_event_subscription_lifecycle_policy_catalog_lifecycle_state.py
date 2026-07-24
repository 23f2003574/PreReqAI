from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState(
    str,
    Enum,
):
    """
    Operational states a consumer projection execution capability
    registry event subscription lifecycle policy catalog may occupy
    over its lifecycle.

    This enum only names the possible states. It performs no
    transition validation, execution, or catalog construction.
    """

    DRAFT = (
        "draft"
    )

    ACTIVE = (
        "active"
    )

    DEPRECATED = (
        "deprecated"
    )

    ARCHIVED = (
        "archived"
    )
