from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot:
    """
    Immutable capture of a consumer projection execution capability
    registry event subscription lifecycle policy catalog's state at
    a point in time.

    The snapshot is a value object only. It performs no catalog
    construction, no restoration, and no collection management.

    Attributes:
        snapshot_id: The snapshot's unique identifier
        catalog: The catalog exactly as it existed when captured
        created_at: When the snapshot was captured
    """

    snapshot_id: str

    catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    created_at: datetime
