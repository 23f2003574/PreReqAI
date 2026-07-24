from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_metadata import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport:
    """
    Immutable, transferable representation of a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog, suitable for serialization and reconstruction.

    The export is a value object only. It performs no catalog
    construction, no policy lookup, and no validation of its
    contents.

    Attributes:
        metadata: The exported catalog's descriptive metadata
        policies: An immutable, order-preserving mapping of policy
            identifier to lifecycle policy
    """

    metadata: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata
    )

    policies: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ]
