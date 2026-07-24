from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup:
    """
    Immutable point-in-time backup of a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog, independent of any snapshot or archive.

    The backup is a value object only. It performs no catalog
    construction, no recovery, and no verification.

    Attributes:
        backup_id: The backup's unique identifier
        catalog: The catalog exactly as it existed when backed up
        created_at: When the backup was created
    """

    backup_id: str

    catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    created_at: datetime
