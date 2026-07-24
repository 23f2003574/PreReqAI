from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationResult:
    """
    Immutable outcome produced after synchronizing a source consumer
    projection execution capability registry event subscription
    lifecycle policy catalog into a target catalog.

    The result is a value object only. It performs no comparison, no
    reconciliation, and no catalog construction.

    Attributes:
        synchronized_catalog: The resulting immutable catalog after
            reconciliation
        added_policy_identifiers: Identifiers present in the source
            catalog but absent from the target catalog
        updated_policy_identifiers: Identifiers present in both
            catalogs whose policies conflicted and were reconciled
        removed_policy_identifiers: Identifiers present in the
            target catalog but absent from the source catalog
        has_changes: Whether synchronization added, updated, or
            removed any policy
    """

    synchronized_catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    added_policy_identifiers: tuple[
        str,
        ...,
    ]

    updated_policy_identifiers: tuple[
        str,
        ...,
    ]

    removed_policy_identifiers: tuple[
        str,
        ...,
    ]

    has_changes: bool
