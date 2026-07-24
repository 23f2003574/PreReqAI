from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_export import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_export_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExportError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExporter:
    """
    Exports a consumer projection execution capability registry
    event subscription lifecycle policy catalog into an immutable,
    transferable representation.

    The exporter's responsibility is validation and capture of an
    existing catalog's metadata and policies, not construction,
    lookup, or import. It does NOT build catalogs, look up policies,
    import catalogs, mutate its input, persist exports, log, or
    publish events.

    The exporter is:
    - Stateless: No instance state
    - Deterministic: Same catalog always produces the same export
    - Side-effect free: Never mutates its input
    """

    def export(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport:
        """
        Export a policy catalog into its transferable representation.

        Args:
            catalog: The policy catalog to export

        Returns:
            An immutable catalog export preserving the catalog's
            metadata and policy ordering

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExportError:
                If the catalog is None, or its metadata or policies
                are missing
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExportError(
                    "Cannot export a None policy catalog."
                )
            )

        if catalog.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExportError(
                    "Cannot export a policy catalog with missing metadata."
                )
            )

        if catalog.policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExportError(
                    "Cannot export a policy catalog with None policies."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport(
                metadata=catalog.metadata,

                policies=MappingProxyType(
                    dict(
                        catalog.policies
                    )
                ),
            )
        )
