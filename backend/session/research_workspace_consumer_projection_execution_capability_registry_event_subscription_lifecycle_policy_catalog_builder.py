from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder:
    """
    Builds an immutable catalog of consumer projection execution
    capability registry event subscription lifecycle policies from
    catalog metadata and a collection of identified policies.

    The builder's responsibility is validation and capture of the
    metadata and policies, not lookup, discovery, or evaluation. It
    does NOT look up policies, discover policies, evaluate policies,
    execute lifecycle transitions, mutate its inputs, persist
    catalogs, log, or publish events.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same metadata and policies always produce the
      same catalog
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        metadata,

        policies,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog:
        """
        Build a policy catalog from catalog metadata and a
        collection of identified policies.

        Args:
            metadata: The catalog's descriptive metadata
            policies: A mapping, or an iterable of (identifier,
                policy) pairs, of policy identifier to lifecycle
                policy

        Returns:
            An immutable policy catalog whose policies preserve the
            order in which they were supplied

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError:
                If the metadata or policies is None, any policy
                identifier is empty or duplicated, or any policy is
                None
        """

        if metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError(
                    "Cannot build a policy catalog with None metadata."
                )
            )

        if policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError(
                    "Cannot build a policy catalog with None policies."
                )
            )

        if hasattr(
            policies,
            "items",
        ):

            entries = list(
                policies.items()
            )

        else:

            entries = list(
                policies
            )

        ordered_policies = {}

        for identifier, policy in entries:

            if not identifier:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError(
                        "Cannot build a policy catalog with an empty policy "
                        "identifier."
                    )
                )

            if identifier in ordered_policies:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError(
                        "Cannot build a policy catalog with duplicate policy "
                        f"identifier '{identifier}'."
                    )
                )

            if policy is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError(
                        "Cannot build a policy catalog with a None policy for "
                        f"identifier '{identifier}'."
                    )
                )

            ordered_policies[identifier] = policy

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
                metadata=metadata,

                policies=MappingProxyType(
                    ordered_policies
                ),
            )
        )
