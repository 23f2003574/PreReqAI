from datetime import (
    datetime,
    timezone,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_archive import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchive,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_archive_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_archive_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService:
    """
    Archives, restores, and looks up consumer projection execution
    capability registry event subscription lifecycle policy
    catalogs without affecting any active catalog instance.

    The service's responsibility is archival, restoration, and
    lookup, not catalog mutation, evaluation, or synchronization.
    It does NOT build catalogs from scratch, mutate catalogs,
    evaluate policies, execute lifecycle transitions, persist
    archives, log, or publish events.

    The service is:
    - Stateless: No instance state
    - Deterministic: Same collection and archive ID always produce
      the same lookup, listing, or restoration outcome
    - Side-effect free: Never mutates its inputs
    """

    def archive(

        self,

        collection,

        catalog,

        archive_id,

        reason,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection:
        """
        Archive a policy catalog into a new archive collection.

        Args:
            collection: The existing archive collection to extend
            catalog: The policy catalog to archive
            archive_id: The unique identifier this archive should
                carry
            reason: Why the catalog is being archived

        Returns:
            A new immutable archive collection with the catalog
            archived; the original collection is left unchanged

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError:
                If the collection, catalog, archive ID, or reason is
                None, the archive ID is blank, or the archive ID
                duplicates one already in the collection
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot archive into a None archive collection."
                )
            )

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot archive a None policy catalog."
                )
            )

        if archive_id is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot archive a policy catalog with a None archive ID."
                )
            )

        if not archive_id:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot archive a policy catalog with a blank archive ID."
                )
            )

        if reason is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot archive a policy catalog with a None reason."
                )
            )

        for existing_archive in collection.archives:

            if existing_archive.archive_id == archive_id:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                        f"Cannot archive with duplicate archive ID '{archive_id}'."
                    )
                )

        new_archive = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchive(
                archive_id=archive_id,

                catalog=catalog,

                archived_at=datetime.now(
                    timezone.utc
                ),

                reason=reason,
            )
        )

        updated_archives = collection.archives + (
            new_archive,
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection(
                archives=updated_archives,

                total_archives=len(
                    updated_archives
                ),
            )
        )

    def restore(

        self,

        collection,

        archive_id,

    ):
        """
        Restore the policy catalog carried by an archive.

        Args:
            collection: The archive collection to restore from
            archive_id: The archive ID to restore

        Returns:
            The catalog exactly as it was archived; the archive
            itself is left unchanged

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError:
                If the collection or archive ID is None, or no
                archive in the collection carries that ID
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot restore from a None archive collection."
                )
            )

        if archive_id is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot restore with a None archive ID."
                )
            )

        for archive in collection.archives:

            if archive.archive_id == archive_id:

                return archive.catalog

        raise (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                f"Cannot restore: no archive found for ID '{archive_id}'."
            )
        )

    def find(

        self,

        collection,

        archive_id,

    ):
        """
        Find the archive registered under an archive ID.

        Args:
            collection: The archive collection to search
            archive_id: The archive ID to look up

        Returns:
            The matching archive, or None if no archive in the
            collection carries that ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError:
                If the collection or archive ID is None
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot search a None archive collection."
                )
            )

        if archive_id is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot search an archive collection with a None archive ID."
                )
            )

        for archive in collection.archives:

            if archive.archive_id == archive_id:

                return archive

        return None

    def list(

        self,

        collection,

    ) -> tuple:
        """
        List every archive in an archive collection.

        Args:
            collection: The archive collection to list

        Returns:
            An immutable tuple of every archive in the collection,
            preserving insertion order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError:
                If the collection is None
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError(
                    "Cannot list archives from a None archive collection."
                )
            )

        return tuple(
            collection.archives
        )
