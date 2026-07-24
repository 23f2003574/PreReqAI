from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_archive import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchive,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection:
    """
    Immutable, ordered collection of consumer projection execution
    capability registry event subscription lifecycle policy catalog
    archives.

    The collection is a value object only. It performs no
    archiving, no lookup, and no restoration.

    Attributes:
        archives: The archives, in insertion order
        total_archives: The number of archives in the collection
    """

    archives: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchive,
        ...,
    ]

    total_archives: int
