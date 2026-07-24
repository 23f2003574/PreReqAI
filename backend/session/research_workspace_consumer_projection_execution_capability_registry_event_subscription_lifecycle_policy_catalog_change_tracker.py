from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_change import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_change_set import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeSet,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_change_tracking_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_change_type import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker:
    """
    Tracks changes between two versions of a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog.

    The tracker's responsibility is comparison of two existing
    catalogs into a reusable summary, not construction, mutation, or
    reconciliation. It does NOT build catalogs, synchronize
    catalogs, evaluate policies, execute lifecycle transitions,
    mutate either input catalog, persist change sets, log, or
    publish events.

    The tracker is:
    - Stateless: No instance state
    - Deterministic: Same previous catalog and current catalog
      always produce the same change set
    - Side-effect free: Never mutates either input catalog
    """

    def track(

        self,

        previous_catalog,

        current_catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeSet:
        """
        Track every change between a previous and a current version
        of a policy catalog.

        Args:
            previous_catalog: The catalog representing the earlier
                state
            current_catalog: The catalog representing the later
                state

        Returns:
            An immutable change set describing every addition,
            update, and removal, preserving each catalog's ordering

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError:
                If either catalog is None, or either catalog's
                policies contain an empty or duplicate identifier or
                a None policy
        """

        if previous_catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError(
                    "Cannot track changes with a None previous catalog."
                )
            )

        if current_catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError(
                    "Cannot track changes with a None current catalog."
                )
            )

        previous_items = self._ordered_items(
            previous_catalog.policies,

            "previous",
        )

        current_items = self._ordered_items(
            current_catalog.policies,

            "current",
        )

        previous_policies = dict(previous_items)
        current_policies = dict(current_items)

        previous_identifiers = [
            identifier

            for identifier, _ in previous_items
        ]

        current_identifiers = [
            identifier

            for identifier, _ in current_items
        ]

        previous_identifier_set = set(previous_identifiers)
        current_identifier_set = set(current_identifiers)

        added_changes = tuple(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange(
                policy_identifier=identifier,

                change_type=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType.ADDED,
            )

            for identifier in current_identifiers

            if identifier not in previous_identifier_set
        )

        updated_changes = tuple(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange(
                policy_identifier=identifier,

                change_type=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType.UPDATED,
            )

            for identifier in current_identifiers

            if (

                identifier in previous_identifier_set

                and current_policies[identifier] != previous_policies[identifier]
            )
        )

        removed_changes = tuple(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChange(
                policy_identifier=identifier,

                change_type=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType.REMOVED,
            )

            for identifier in previous_identifiers

            if identifier not in current_identifier_set
        )

        total_changes = (
            len(added_changes)

            + len(updated_changes)

            + len(removed_changes)
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeSet(
                added_changes=added_changes,

                updated_changes=updated_changes,

                removed_changes=removed_changes,

                total_changes=total_changes,

                has_changes=(
                    total_changes > 0
                ),
            )
        )

    def _ordered_items(

        self,

        policies,

        label,

    ) -> list:

        if policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError(
                    f"Cannot track changes with None {label} catalog policies."
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
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError(
                        f"Cannot track changes for a {label} catalog with an empty "
                        "policy identifier."
                    )
                )

            if identifier in seen_identifiers:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError(
                        f"Cannot track changes for a {label} catalog with duplicate "
                        f"policy identifier '{identifier}'."
                    )
                )

            if policy is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError(
                        f"Cannot track changes for a {label} catalog with a None "
                        f"policy for identifier '{identifier}'."
                    )
                )

            seen_identifiers.add(
                identifier
            )

        return items
