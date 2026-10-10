from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_builder import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_import_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_import_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter:
    """
    Imports a consumer projection execution capability registry
    event subscription lifecycle policy catalog from its exported
    representation.

    The importer's responsibility is validation and reconstruction
    of a catalog from an export, not export, lookup, or evaluation.
    It does NOT export catalogs, look up policies, evaluate policies,
    execute lifecycle transitions, mutate its input, persist
    imports, log, or publish events.

    The importer is:
    - Stateless: No instance state
    - Deterministic: Same export always produces the same import
      result
    - Side-effect free: Never mutates its input
    """

    def import_catalog(

        self,

        export,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportResult:
        """
        Import a policy catalog from its exported representation.

        Args:
            export: The catalog export to rebuild a catalog from

        Returns:
            An immutable import result carrying the rebuilt catalog
            and the number of policies imported

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError:
                If the export is None, its metadata or policies are
                missing, its structure is invalid, or its policies
                contain duplicate or empty identifiers or None
                policies
        """

        if export is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError(
                    "Cannot import from a None catalog export."
                )
            )

        if export.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError(
                    "Cannot import a catalog export with missing metadata."
                )
            )

        if export.policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError(
                    "Cannot import a catalog export with None policies."
                )
            )

        try:

            catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                export.metadata,

                export.policies,
            )

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError(
                    f"Cannot import a catalog export: {error}"
                )
            ) from error

        except (TypeError, AttributeError) as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError(
                    f"Cannot import a catalog export with an invalid structure: {error}"
                )
            ) from error

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportResult(
                catalog=catalog,

                imported_policy_count=len(
                    catalog.policies
                ),
            )
        )
