from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_snapshot_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_snapshot_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager:
    """
    Creates, collects, looks up, and restores immutable snapshots of
    a consumer projection execution capability registry event
    subscription lifecycle policy catalog.

    The manager's responsibility is snapshot capture, collection
    assembly, lookup, and restoration, not catalog mutation,
    evaluation, or synchronization. It does NOT build catalogs from
    scratch, mutate catalogs, evaluate policies, execute lifecycle
    transitions, persist snapshots, log, or publish events.

    The manager is:
    - Stateless: No instance state
    - Deterministic: Same snapshot or collection always produces the
      same lookup, listing, or restoration outcome
    - Side-effect free: Never mutates its inputs
    """

    def create_snapshot(

        self,

        catalog,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot:
        """
        Capture a snapshot of a policy catalog's current state.

        Args:
            catalog: The policy catalog to capture

        Returns:
            An immutable snapshot with a freshly generated
            identifier, referencing the catalog exactly as given

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError:
                If the catalog, its metadata, or its policies is None
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot snapshot a None policy catalog."
                )
            )

        if catalog.metadata is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot snapshot a policy catalog with missing metadata."
                )
            )

        if catalog.policies is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot snapshot a policy catalog with None policies."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot(
                snapshot_id=str(
                    uuid4()
                ),

                catalog=catalog,

                created_at=datetime.now(
                    timezone.utc
                ),
            )
        )

    def build_collection(

        self,

        snapshots,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection:
        """
        Build a snapshot collection from a collection of snapshots.

        Args:
            snapshots: The snapshots to assemble, in the order they
                should appear in the collection

        Returns:
            An immutable snapshot collection preserving insertion
            order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError:
                If the snapshots are None, any snapshot is None, or
                any snapshot ID is duplicated
        """

        if snapshots is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot build a snapshot collection with None snapshots."
                )
            )

        snapshots = tuple(
            snapshots
        )

        self._validate_snapshots(
            snapshots
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection(
                snapshots=snapshots,

                total_snapshots=len(
                    snapshots
                ),
            )
        )

    def add_snapshot(

        self,

        collection,

        snapshot,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection:
        """
        Add a single snapshot to an existing snapshot collection,
        producing a new snapshot collection.

        Args:
            collection: The existing snapshot collection to extend
            snapshot: The snapshot to add

        Returns:
            A new immutable snapshot collection with the snapshot
            appended; the original collection is left unchanged

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError:
                If the collection or snapshot is None, or the
                snapshot's ID duplicates one already in the
                collection
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot add a snapshot to a None snapshot collection."
                )
            )

        if snapshot is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot add a None snapshot to a snapshot collection."
                )
            )

        updated_snapshots = collection.snapshots + (
            snapshot,
        )

        self._validate_snapshots(
            updated_snapshots
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection(
                snapshots=updated_snapshots,

                total_snapshots=len(
                    updated_snapshots
                ),
            )
        )

    def find_snapshot(

        self,

        collection,

        snapshot_id,

    ):
        """
        Find the snapshot registered under a snapshot ID.

        Args:
            collection: The snapshot collection to search
            snapshot_id: The snapshot ID to look up

        Returns:
            The matching snapshot, or None if no snapshot in the
            collection carries that ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError:
                If the collection or snapshot ID is None
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot search a None snapshot collection."
                )
            )

        if snapshot_id is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot search a snapshot collection with a None snapshot ID."
                )
            )

        for snapshot in collection.snapshots:

            if snapshot.snapshot_id == snapshot_id:

                return snapshot

        return None

    def list_snapshots(

        self,

        collection,

    ) -> tuple:
        """
        List every snapshot in a snapshot collection.

        Args:
            collection: The snapshot collection to list

        Returns:
            An immutable tuple of every snapshot in the collection,
            preserving insertion order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError:
                If the collection is None
        """

        if collection is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot list snapshots from a None snapshot collection."
                )
            )

        return tuple(
            collection.snapshots
        )

    def restore_snapshot(

        self,

        snapshot,

    ):
        """
        Restore the policy catalog captured by a snapshot.

        Args:
            snapshot: The snapshot to restore from

        Returns:
            The catalog exactly as it was captured; the snapshot
            itself is left unchanged

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError:
                If the snapshot or its catalog is None
        """

        if snapshot is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot restore a None snapshot."
                )
            )

        if snapshot.catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                    "Cannot restore a snapshot with a None catalog."
                )
            )

        return snapshot.catalog

    def _validate_snapshots(

        self,

        snapshots,

    ) -> None:

        seen_snapshot_ids = set()

        for snapshot in snapshots:

            if snapshot is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                        "Cannot build a snapshot collection with a None snapshot."
                    )
                )

            if snapshot.snapshot_id in seen_snapshot_ids:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError(
                        "Cannot build a snapshot collection with duplicate "
                        f"snapshot ID '{snapshot.snapshot_id}'."
                    )
                )

            seen_snapshot_ids.add(
                snapshot.snapshot_id
            )
