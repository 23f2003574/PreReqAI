from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_search_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_search_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService:
    """
    Searches a consumer projection execution capability registry
    event subscription lifecycle policy catalog for policies
    matching a set of search criteria.

    The service's responsibility is read-only filtering, not
    construction, mutation, or evaluation. It does NOT build
    catalogs, mutate catalogs, evaluate policies, execute lifecycle
    transitions, persist data, log, or publish events.

    The service is:
    - Stateless: No instance state
    - Deterministic: Same catalog and criteria always produce the
      same result
    - Side-effect free: Never mutates its inputs
    """

    def search(

        self,

        catalog,

        criteria,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchResult:
        """
        Search a policy catalog for policies matching the given
        criteria.

        Filters are applied, in order, as: include identifiers,
        exclude identifiers, identifier prefix, then identifier
        substring. A policy must satisfy every filter set on the
        criteria to match.

        Args:
            catalog: The policy catalog to search
            criteria: The search criteria to match policies against

        Returns:
            An immutable search result preserving catalog ordering

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError:
                If the catalog or criteria is None
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError(
                    "Cannot search a None policy catalog."
                )
            )

        if criteria is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError(
                    "Cannot search a policy catalog with None criteria."
                )
            )

        include_identifiers = (
            set(
                criteria.include_identifiers
            )

            if criteria.include_identifiers is not None

            else None
        )

        exclude_identifiers = (
            set(
                criteria.exclude_identifiers
            )

            if criteria.exclude_identifiers is not None

            else set()
        )

        matched_policies = {}

        for identifier, policy in catalog.policies.items():

            if (

                include_identifiers is not None

                and identifier not in include_identifiers
            ):

                continue

            if identifier in exclude_identifiers:

                continue

            if (

                criteria.identifier_prefix is not None

                and not identifier.startswith(
                    criteria.identifier_prefix
                )
            ):

                continue

            if (

                criteria.identifier_contains is not None

                and criteria.identifier_contains not in identifier
            ):

                continue

            matched_policies[identifier] = policy

        matched_policies = MappingProxyType(
            matched_policies
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchResult(
                matched_policies=matched_policies,

                total_matches=len(
                    matched_policies
                ),
            )
        )
