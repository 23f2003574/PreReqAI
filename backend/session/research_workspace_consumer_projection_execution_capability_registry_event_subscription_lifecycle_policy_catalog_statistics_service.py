from datetime import (
    datetime,
    timezone,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_statistics import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_statistics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_statistics_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsReport,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService:
    """
    Generates summary statistics for a consumer projection execution
    capability registry event subscription lifecycle policy
    catalog.

    The service's responsibility is read-only computation of
    catalog-level statistics, not construction, mutation, search, or
    evaluation. It does NOT build catalogs, mutate catalogs, search
    catalogs, evaluate policies, execute lifecycle transitions,
    persist reports, log, or publish events.

    The service is:
    - Stateless: No instance state
    - Deterministic: Same catalog always produces the same
      statistics
    - Side-effect free: Never mutates its input
    """

    def generate(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsReport:
        """
        Generate a statistics report for a policy catalog.

        Args:
            catalog: The policy catalog to summarize

        Returns:
            An immutable statistics report reflecting the catalog's
            ordering at the time of generation

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsError:
                If the catalog or its policies is None
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsError(
                    "Cannot generate statistics for a None policy catalog."
                )
            )

        if catalog.policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsError(
                    "Cannot generate statistics for a policy catalog with None "
                    "policies."
                )
            )

        identifiers = list(
            catalog.policies.keys()
        )

        total_policies = len(
            identifiers
        )

        unique_policy_identifiers = len(
            set(
                identifiers
            )
        )

        statistics = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics(
                total_policies=total_policies,

                unique_policy_identifiers=unique_policy_identifiers,

                first_policy_identifier=(
                    identifiers[0]

                    if identifiers

                    else None
                ),

                last_policy_identifier=(
                    identifiers[-1]

                    if identifiers

                    else None
                ),

                empty_catalog=(
                    total_policies == 0
                ),
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsReport(
                statistics=statistics,

                generated_at=datetime.now(
                    timezone.utc
                ),
            )
        )
