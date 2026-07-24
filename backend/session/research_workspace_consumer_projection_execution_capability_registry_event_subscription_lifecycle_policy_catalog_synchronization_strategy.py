from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy(
    str,
    Enum,
):
    """
    Strategies for resolving conflicting policies when synchronizing
    a source consumer projection execution capability registry event
    subscription lifecycle policy catalog into a target catalog.

    This enum only names the possible strategies. It performs no
    comparison, reconciliation, or catalog construction.
    """

    PREFER_SOURCE = (
        "prefer_source"
    )

    PREFER_TARGET = (
        "prefer_target"
    )

    FAIL_ON_CONFLICT = (
        "fail_on_conflict"
    )
