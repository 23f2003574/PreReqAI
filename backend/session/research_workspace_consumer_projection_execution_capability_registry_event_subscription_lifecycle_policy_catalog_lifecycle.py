from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycle:
    """
    Immutable record of a consumer projection execution capability
    registry event subscription lifecycle policy catalog's current
    operational state and the timestamps at which it reached each
    milestone.

    The lifecycle is a value object only. It performs no transition
    validation, no execution, and no catalog construction.

    Attributes:
        state: The catalog's current lifecycle state
        activated_at: When the catalog was activated, or None if it
            has never been activated
        deprecated_at: When the catalog was deprecated, or None if
            it has never been deprecated
        archived_at: When the catalog was archived, or None if it
            has never been archived
    """

    state: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState
    )

    activated_at: (
        datetime | None
    )

    deprecated_at: (
        datetime | None
    )

    archived_at: (
        datetime | None
    )
