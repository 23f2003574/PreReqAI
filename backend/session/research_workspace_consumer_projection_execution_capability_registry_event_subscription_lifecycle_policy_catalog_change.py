from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_change_type import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange:
    """
    Immutable record of a single policy's change between two
    versions of a consumer projection execution capability registry
    event subscription lifecycle policy catalog.

    The change is a value object only. It performs no comparison,
    no tracking, and no catalog construction.

    Attributes:
        policy_identifier: The identifier of the policy that changed
        change_type: The kind of change the policy underwent
    """

    policy_identifier: str

    change_type: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType
    )
