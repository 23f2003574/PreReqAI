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
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog:
    """
    Immutable collection of consumer projection execution capability
    registry event subscription lifecycle policies, organized under
    a single set of catalog metadata and addressed by identifier.

    The catalog is a value object only. It performs no policy
    lookup, no discovery, and no validation of its policies. Lookup
    and discovery are the responsibility of a catalog service;
    validation is the responsibility of a catalog builder.

    Attributes:
        metadata: The catalog's descriptive metadata
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
