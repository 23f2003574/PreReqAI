from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_builder import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_synchronization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_synchronization_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_synchronization_strategy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer:
    """
    Synchronizes a source consumer projection execution capability
    registry event subscription lifecycle policy catalog into a
    target catalog, producing a new, reconciled, immutable catalog.

    The synchronizer's responsibility is comparison and
    reconciliation of two existing catalogs, not construction of
    catalogs from scratch, lookup, or evaluation. It does NOT
    evaluate policies, execute lifecycle transitions, mutate either
    input catalog, persist results, log, or publish events.

    The synchronizer is:
    - Stateless: No instance state
    - Deterministic: Same source catalog, target catalog, and
      strategy always produce the same result
    - Side-effect free: Never mutates either input catalog
    """

    def synchronize(

        self,

        source_catalog,

        target_catalog,

        strategy,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationResult:
        """
        Synchronize a source policy catalog into a target policy
        catalog.

        Policies present in the source catalog but absent from the
        target catalog are added. Policies present in the target
        catalog but absent from the source catalog are removed.
        Policies present in both catalogs whose content conflicts
        are reconciled according to the given strategy. The
        resulting catalog preserves the target catalog's ordering
        for retained identifiers, followed by newly added
        identifiers in source order.

        Args:
            source_catalog: The catalog whose policies are being
                synchronized in
            target_catalog: The catalog being reconciled against the
                source catalog
            strategy: The strategy used to resolve conflicting
                policies

        Returns:
            An immutable synchronization result carrying the
            reconciled catalog and the identifiers that were added,
            updated, and removed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError:
                If either catalog or the strategy is None, the
                strategy is not a recognized synchronization
                strategy, either catalog's policies contain an
                empty or duplicate identifier or a None policy, or
                a conflict is found while using the FAIL_ON_CONFLICT
                strategy
        """

        if source_catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                    "Cannot synchronize a None source catalog."
                )
            )

        if target_catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                    "Cannot synchronize a None target catalog."
                )
            )

        if strategy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                    "Cannot synchronize policy catalogs with a None strategy."
                )
            )

        if not isinstance(

            strategy,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                    f"Cannot synchronize policy catalogs with an invalid strategy: {strategy!r}."
                )
            )

        source_items = self._ordered_items(
            source_catalog.policies,

            "source",
        )

        target_items = self._ordered_items(
            target_catalog.policies,

            "target",
        )

        source_policies = dict(source_items)
        target_policies = dict(target_items)

        source_identifiers = [
            identifier

            for identifier, _ in source_items
        ]

        target_identifiers = [
            identifier

            for identifier, _ in target_items
        ]

        source_identifier_set = set(source_identifiers)
        target_identifier_set = set(target_identifiers)

        added_policy_identifiers = tuple(
            identifier

            for identifier in source_identifiers

            if identifier not in target_identifier_set
        )

        removed_policy_identifiers = tuple(
            identifier

            for identifier in target_identifiers

            if identifier not in source_identifier_set
        )

        conflicting_identifiers = tuple(
            identifier

            for identifier in target_identifiers

            if (

                identifier in source_identifier_set

                and source_policies[identifier] != target_policies[identifier]
            )
        )

        if (

            strategy
            is ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy.FAIL_ON_CONFLICT

            and conflicting_identifiers
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                    "Cannot synchronize policy catalogs: unresolved conflicts for "
                    f"identifiers {list(conflicting_identifiers)!r}."
                )
            )

        conflicting_identifier_set = set(conflicting_identifiers)

        merged_policies = {}

        for identifier in target_identifiers:

            if identifier not in source_identifier_set:

                continue

            if identifier in conflicting_identifier_set:

                merged_policies[identifier] = (
                    source_policies[identifier]

                    if strategy
                    is ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy.PREFER_SOURCE

                    else target_policies[identifier]
                )

            else:

                merged_policies[identifier] = target_policies[identifier]

        for identifier in source_identifiers:

            if identifier not in target_identifier_set:

                merged_policies[identifier] = source_policies[identifier]

        synchronized_catalog = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                target_catalog.metadata,

                merged_policies,
            )
        )

        has_changes = bool(
            added_policy_identifiers

            or conflicting_identifiers

            or removed_policy_identifiers
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationResult(
                synchronized_catalog=synchronized_catalog,

                added_policy_identifiers=added_policy_identifiers,

                updated_policy_identifiers=conflicting_identifiers,

                removed_policy_identifiers=removed_policy_identifiers,

                has_changes=has_changes,
            )
        )

    def _ordered_items(

        self,

        policies,

        label,

    ) -> list:

        if policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                    f"Cannot synchronize with None {label} catalog policies."
                )
            )

        if hasattr(

            policies,

            "items",
        ):

            items = list(
                policies.items()
            )

        else:

            items = list(
                policies
            )

        seen_identifiers = set()

        for identifier, policy in items:

            if not identifier:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                        f"Cannot synchronize a {label} catalog with an empty policy "
                        "identifier."
                    )
                )

            if identifier in seen_identifiers:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                        f"Cannot synchronize a {label} catalog with duplicate policy "
                        f"identifier '{identifier}'."
                    )
                )

            if policy is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError(
                        f"Cannot synchronize a {label} catalog with a None policy for "
                        f"identifier '{identifier}'."
                    )
                )

            seen_identifiers.add(
                identifier
            )

        return items
