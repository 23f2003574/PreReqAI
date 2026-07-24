from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_metadata_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata:
    """
    Immutable descriptive metadata identifying a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog.

    The metadata is a value object only. It performs no policy
    lookup, no catalog construction, and no validation of a
    catalog's policies.

    Attributes:
        catalog_name: The catalog's name
        catalog_version: The catalog's version
        description: A human-readable description of the catalog
    """

    catalog_name: str

    catalog_version: str

    description: str

    def __post_init__(self):

        if not self.catalog_name:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError(
                    "Cannot build catalog metadata with an empty catalog name."
                )
            )

        if not self.catalog_version:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError(
                    "Cannot build catalog metadata with an empty catalog version."
                )
            )
