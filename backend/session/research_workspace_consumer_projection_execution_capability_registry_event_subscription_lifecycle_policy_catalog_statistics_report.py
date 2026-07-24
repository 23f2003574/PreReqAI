from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_statistics import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsReport:
    """
    Immutable report produced after generating summary statistics
    for a consumer projection execution capability registry event
    subscription lifecycle policy catalog.

    The report is a value object only. It performs no computation,
    no catalog lookup, and no persistence.

    Attributes:
        statistics: The catalog's summary statistics
        generated_at: When this report was generated
    """

    statistics: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics
    )

    generated_at: datetime
