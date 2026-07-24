from datetime import datetime

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager,
)


REGISTERED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED
ACTIVE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            REGISTERED,
            ACTIVE,
        ),
        initial_state,
    )


def _build_metadata():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
        catalog_name="core-lifecycle-policies",

        catalog_version="1.0.0",

        description="Core lifecycle policy catalog.",
    )


def _build_catalog(policies):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
        _build_metadata(),

        policies,
    )


class TestCreateSnapshot:
    """A snapshot can be captured from a policy catalog."""

    def test_create_snapshot(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().create_snapshot(
            catalog
        )

        assert isinstance(
            snapshot,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot,
        )
        assert snapshot.catalog is catalog
        assert isinstance(snapshot.snapshot_id, str)
        assert snapshot.snapshot_id != ""
        assert isinstance(snapshot.created_at, datetime)


class TestCreateMultipleSnapshots:
    """Multiple snapshots can be captured and collected."""

    def test_create_multiple_snapshots(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        first_catalog = _build_catalog({})
        second_catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        first_snapshot = manager.create_snapshot(first_catalog)
        second_snapshot = manager.create_snapshot(second_catalog)

        collection = manager.build_collection(
            (
                first_snapshot,
                second_snapshot,
            )
        )

        assert collection.total_snapshots == 2
        assert first_snapshot.snapshot_id != second_snapshot.snapshot_id


class TestRestoreSnapshot:
    """Restoring a snapshot returns the exact catalog it captured."""

    def test_restore_snapshot(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        snapshot = manager.create_snapshot(catalog)

        restored_catalog = manager.restore_snapshot(snapshot)

        assert restored_catalog is catalog


class TestLookupExistingSnapshot:
    """find_snapshot() returns the snapshot registered under its ID."""

    def test_lookup_existing_snapshot(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        snapshot = manager.create_snapshot(
            _build_catalog({})
        )

        collection = manager.build_collection(
            (
                snapshot,
            )
        )

        found = manager.find_snapshot(
            collection,

            snapshot.snapshot_id,
        )

        assert found is snapshot


class TestLookupMissingSnapshot:
    """find_snapshot() returns None for an unregistered ID."""

    def test_lookup_missing_snapshot(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        collection = manager.build_collection(())

        assert manager.find_snapshot(
            collection,

            "missing",
        ) is None


class TestListPreservesOrder:
    """list_snapshots() preserves insertion order."""

    def test_list_preserves_order(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        first_snapshot = manager.create_snapshot(_build_catalog({}))
        second_snapshot = manager.create_snapshot(_build_catalog({}))

        collection = manager.build_collection(
            (
                first_snapshot,
                second_snapshot,
            )
        )

        assert manager.list_snapshots(collection) == (
            first_snapshot,
            second_snapshot,
        )


class TestTotalSnapshotsUpdated:
    """total_snapshots reflects the current count after add_snapshot()."""

    def test_total_snapshots_updated(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        collection = manager.build_collection(
            (
                manager.create_snapshot(_build_catalog({})),
            )
        )

        assert collection.total_snapshots == 1

        collection = manager.add_snapshot(
            collection,

            manager.create_snapshot(_build_catalog({})),
        )

        assert collection.total_snapshots == 2


class TestImmutableSnapshotCollection:
    """add_snapshot() returns a new collection without mutating the original."""

    def test_immutable_snapshot_collection(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        original = manager.build_collection(
            (
                manager.create_snapshot(_build_catalog({})),
            )
        )

        updated = manager.add_snapshot(
            original,

            manager.create_snapshot(_build_catalog({})),
        )

        assert original.total_snapshots == 1
        assert updated.total_snapshots == 2
        assert original is not updated

        assert isinstance(
            updated,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotCollection,
        )


class TestRejectDuplicateSnapshotIds:
    """Duplicate snapshot IDs are rejected."""

    def test_reject_duplicate_snapshot_ids_on_build(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        snapshot = manager.create_snapshot(_build_catalog({}))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            manager.build_collection(
                (
                    snapshot,
                    snapshot,
                )
            )

    def test_reject_duplicate_snapshot_id_on_add(self):
        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager()

        snapshot = manager.create_snapshot(_build_catalog({}))

        collection = manager.build_collection(
            (
                snapshot,
            )
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            manager.add_snapshot(
                collection,

                snapshot,
            )


class TestRejectInvalidInputs:
    """None inputs and invalid catalogs or snapshots are rejected."""

    def test_reject_none_catalog_on_create(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().create_snapshot(
                None
            )

    def test_reject_invalid_catalog_missing_metadata(self):
        malformed_catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=None,

            policies={},
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().create_snapshot(
                malformed_catalog
            )

    def test_reject_none_collection_on_find(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().find_snapshot(
                None,

                "some-id",
            )

    def test_reject_none_collection_on_list(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().list_snapshots(
                None
            )

    def test_reject_none_snapshot_on_restore(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().restore_snapshot(
                None
            )

    def test_reject_invalid_snapshot_missing_catalog(self):
        malformed_snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshot(
            snapshot_id="broken",

            catalog=None,

            created_at=datetime.now(),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSnapshotManager().restore_snapshot(
                malformed_snapshot
            )
