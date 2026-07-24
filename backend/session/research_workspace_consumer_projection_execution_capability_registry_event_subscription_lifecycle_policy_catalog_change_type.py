from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType(
    str,
    Enum,
):
    """
    Kinds of change a single policy can undergo between two versions
    of a consumer projection execution capability registry event
    subscription lifecycle policy catalog.

    This enum only names the possible change types. It performs no
    comparison, tracking, or catalog construction.
    """

    ADDED = (
        "added"
    )

    UPDATED = (
        "updated"
    )

    REMOVED = (
        "removed"
    )
