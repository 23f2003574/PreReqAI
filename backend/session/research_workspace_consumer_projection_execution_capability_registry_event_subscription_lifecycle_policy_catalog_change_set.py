from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_change import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeSet:
    """
    Immutable summary of every change between two versions of a
    consumer projection execution capability registry event
    subscription lifecycle policy catalog.

    The change set is a value object only. It performs no
    comparison, no tracking, and no catalog construction.

    Attributes:
        added_changes: Changes for policies present in the current
            catalog but absent from the previous catalog
        updated_changes: Changes for policies present in both
            catalogs whose content differs
        removed_changes: Changes for policies present in the
            previous catalog but absent from the current catalog
        total_changes: The total number of added, updated, and
            removed changes
        has_changes: Whether any change was detected
    """

    added_changes: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange,
        ...,
    ]

    updated_changes: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange,
        ...,
    ]

    removed_changes: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange,
        ...,
    ]

    total_changes: int

    has_changes: bool
