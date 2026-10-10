from datetime import datetime

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
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


def _empty_collection():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection(
        archives=(),

        total_archives=0,
    )


class TestArchiveCatalog:
    """A catalog can be archived into a new archive collection."""

    def test_archive_catalog(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        collection = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().archive(
            _empty_collection(),

            catalog,

            "archive-1",

            "rotation",
        )

        assert isinstance(
            collection,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveCollection,
        )
        assert collection.total_archives == 1
        assert collection.archives[0].archive_id == "archive-1"
        assert collection.archives[0].catalog is catalog
        assert collection.archives[0].reason == "rotation"
        assert isinstance(collection.archives[0].archived_at, datetime)


class TestArchiveMultipleCatalogs:
    """Multiple catalogs can be archived into the same collection."""

    def test_archive_multiple_catalogs(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        collection = service.archive(
            _empty_collection(),

            _build_catalog({}),

            "archive-1",

            "rotation",
        )

        collection = service.archive(
            collection,

            _build_catalog(
                {
                    "registered-default": _build_policy(REGISTERED),
                }
            ),

            "archive-2",

            "manual-backup",
        )

        assert collection.total_archives == 2


class TestRestoreArchivedCatalog:
    """Restoring an archive returns the exact catalog it captured."""

    def test_restore_archived_catalog(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        collection = service.archive(
            _empty_collection(),

            catalog,

            "archive-1",

            "rotation",
        )

        restored_catalog = service.restore(
            collection,

            "archive-1",
        )

        assert restored_catalog is catalog


class TestFindExistingArchive:
    """find() returns the archive registered under its archive ID."""

    def test_find_existing_archive(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        collection = service.archive(
            _empty_collection(),

            _build_catalog({}),

            "archive-1",

            "rotation",
        )

        found = service.find(
            collection,

            "archive-1",
        )

        assert found is not None
        assert found.archive_id == "archive-1"


class TestFindMissingArchive:
    """find() returns None for an unregistered archive ID."""

    def test_find_missing_archive(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        assert service.find(
            _empty_collection(),

            "missing",
        ) is None


class TestPreserveOrdering:
    """list() preserves insertion order."""

    def test_preserve_ordering(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        collection = service.archive(
            _empty_collection(),

            _build_catalog({}),

            "zeta",

            "rotation",
        )

        collection = service.archive(
            collection,

            _build_catalog({}),

            "alpha",

            "manual-backup",
        )

        assert [
            archive.archive_id

            for archive in service.list(collection)
        ] == [
            "zeta",
            "alpha",
        ]


class TestImmutableArchiveCollection:
    """archive() returns a new collection without mutating the original."""

    def test_immutable_archive_collection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        original = _empty_collection()

        updated = service.archive(
            original,

            _build_catalog({}),

            "archive-1",

            "rotation",
        )

        assert original.total_archives == 0
        assert updated.total_archives == 1
        assert original is not updated


class TestRejectDuplicateArchiveIds:
    """Duplicate archive IDs are rejected."""

    def test_reject_duplicate_archive_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService()

        collection = service.archive(
            _empty_collection(),

            _build_catalog({}),

            "archive-1",

            "rotation",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            service.archive(
                collection,

                _build_catalog({}),

                "archive-1",

                "manual-backup",
            )


class TestRejectInvalidInputs:
    """None inputs, blank archive IDs, and missing catalogs are rejected."""

    def test_reject_none_collection_on_archive(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().archive(
                None,

                _build_catalog({}),

                "archive-1",

                "rotation",
            )

    def test_reject_none_catalog_on_archive(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().archive(
                _empty_collection(),

                None,

                "archive-1",

                "rotation",
            )

    def test_reject_none_archive_id_on_archive(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().archive(
                _empty_collection(),

                _build_catalog({}),

                None,

                "rotation",
            )

    def test_reject_blank_archive_id_on_archive(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().archive(
                _empty_collection(),

                _build_catalog({}),

                "",

                "rotation",
            )

    def test_reject_none_reason_on_archive(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().archive(
                _empty_collection(),

                _build_catalog({}),

                "archive-1",

                None,
            )

    def test_reject_none_collection_on_restore(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().restore(
                None,

                "archive-1",
            )

    def test_reject_missing_archive_on_restore(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().restore(
                _empty_collection(),

                "missing",
            )

    def test_reject_none_collection_on_find(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().find(
                None,

                "archive-1",
            )

    def test_reject_none_collection_on_list(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogArchiveService().list(
                None
            )
