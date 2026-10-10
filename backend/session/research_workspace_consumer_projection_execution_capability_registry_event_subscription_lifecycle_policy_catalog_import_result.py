from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportResult:
    """
    Immutable outcome produced after importing a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog from its exported representation.

    The result is a value object only. It performs no import, no
    catalog construction, and no validation.

    Attributes:
        catalog: The rebuilt policy catalog
        imported_policy_count: The number of policies imported into
            the catalog
    """

    catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    imported_policy_count: int
