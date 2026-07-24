from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection:
    """
    Immutable, ordered collection of consumer projection execution
    capability registry event subscription lifecycle policy catalog
    snapshots.

    The collection is a value object only. It performs no snapshot
    creation, no lookup, and no restoration.

    Attributes:
        snapshots: The snapshots, in insertion order
        total_snapshots: The number of snapshots in the collection
    """

    snapshots: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot,
        ...,
    ]

    total_snapshots: int
