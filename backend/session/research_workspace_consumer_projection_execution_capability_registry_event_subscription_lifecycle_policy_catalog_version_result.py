from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionResult:
    """
    Immutable outcome produced after upgrading a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog to a new version.

    The result is a value object only. It performs no upgrade, no
    catalog construction, and no validation.

    Attributes:
        previous_catalog: The catalog exactly as it was before the
            upgrade
        updated_catalog: A new catalog carrying the upgraded
            version, with all policies and their ordering preserved
        version_changed: Whether the upgrade produced a different
            version than the previous catalog
    """

    previous_catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    updated_catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    version_changed: bool
