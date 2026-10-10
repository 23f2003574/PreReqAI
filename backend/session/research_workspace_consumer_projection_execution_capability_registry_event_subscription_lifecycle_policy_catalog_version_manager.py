from datetime import (
    datetime,
    timezone,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_builder import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_metadata import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_version_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager:
    """
    Manages version upgrades and version reads for a consumer
    projection execution capability registry event subscription
    lifecycle policy catalog.

    The manager's responsibility is validation, upgrade, and
    inspection of a catalog's version, not comparison, evaluation,
    or synchronization against another catalog. It does NOT compare
    catalogs, synchronize catalogs, evaluate policies, execute
    lifecycle transitions, mutate its inputs, persist catalogs, log,
    or publish events.

    The manager is:
    - Stateless: No instance state; it tracks no version history
      beyond what a single catalog carries
    - Side-effect free: Never mutates its inputs
    """

    def upgrade(

        self,

        catalog,

        new_version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionResult:
        """
        Upgrade a policy catalog to a new version, producing a new
        catalog that carries the same policies in the same order
        under the new version.

        Args:
            catalog: The policy catalog to upgrade
            new_version: The version the upgraded catalog should
                carry

        Returns:
            An immutable version result carrying the unchanged
            previous catalog and the newly upgraded catalog

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError:
                If the catalog or its metadata is None, the new
                version is not a non-empty string, or the new
                version is identical to the catalog's current
                version
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot upgrade a None policy catalog."
                )
            )

        if catalog.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot upgrade a policy catalog with missing metadata."
                )
            )

        if not isinstance(

            new_version,

            str,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    f"Cannot upgrade a policy catalog with an invalid version: {new_version!r}."
                )
            )

        if not new_version:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot upgrade a policy catalog with an empty version."
                )
            )

        if new_version == catalog.metadata.catalog_version:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot upgrade a policy catalog to its current version "
                    f"'{new_version}'."
                )
            )

        updated_metadata = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
                catalog_name=catalog.metadata.catalog_name,

                catalog_version=new_version,

                description=catalog.metadata.description,
            )
        )

        updated_catalog = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                updated_metadata,

                catalog.policies,
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionResult(
                previous_catalog=catalog,

                updated_catalog=updated_catalog,

                version_changed=True,
            )
        )

    def is_latest(

        self,

        catalog,

    ) -> bool:
        """
        Check whether a policy catalog is at its latest version.

        The manager tracks no external version history, so a valid
        catalog is, by definition, at the latest version it is
        aware of.

        Args:
            catalog: The policy catalog to check

        Returns:
            True, for any catalog with valid metadata

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError:
                If the catalog or its metadata is None
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot check the version of a None policy catalog."
                )
            )

        if catalog.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot check the version of a policy catalog with missing "
                    "metadata."
                )
            )

        return True

    def version(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersion:
        """
        Read a snapshot of a policy catalog's current version.

        Args:
            catalog: The policy catalog to read the version of

        Returns:
            An immutable version snapshot. Its previous_version is
            always None, since a catalog carries no upgrade history
            of its own; only an upgrade() result links a catalog to
            the version it came from.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError:
                If the catalog or its metadata is None
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot read the version of a None policy catalog."
                )
            )

        if catalog.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError(
                    "Cannot read the version of a policy catalog with missing "
                    "metadata."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersion(
                version=catalog.metadata.catalog_version,

                created_at=datetime.now(
                    timezone.utc
                ),

                previous_version=None,
            )
        )
