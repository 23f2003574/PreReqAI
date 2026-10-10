from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchive:
    """
    Immutable archival record of a consumer projection execution
    capability registry event subscription lifecycle policy
    catalog, captured at the moment it was archived.

    The archive is a value object only. It performs no catalog
    construction, no restoration, and no collection management.

    Attributes:
        archive_id: The archive's unique identifier
        catalog: The catalog exactly as it existed when archived
        archived_at: When the catalog was archived
        reason: Why the catalog was archived
    """

    archive_id: str

    catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    archived_at: datetime

    reason: str
