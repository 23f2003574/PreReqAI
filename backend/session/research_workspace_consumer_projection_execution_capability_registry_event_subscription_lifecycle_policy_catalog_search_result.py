from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchResult:
    """
    Immutable outcome produced after searching a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog.

    The result is a value object only. It performs no search and no
    catalog lookup.

    Attributes:
        matched_policies: An immutable, order-preserving mapping of
            policy identifier to lifecycle policy for every policy
            that matched the search criteria
        total_matches: The number of policies that matched the
            search criteria
    """

    matched_policies: Mapping[
        str,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ]

    total_matches: int
