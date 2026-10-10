from datetime import datetime

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionResult,
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


def _build_metadata(catalog_version="1.0.0"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
        catalog_name="core-lifecycle-policies",

        catalog_version=catalog_version,

        description="Core lifecycle policy catalog.",
    )


def _build_catalog(policies, catalog_version="1.0.0"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
        _build_metadata(catalog_version),

        policies,
    )


class TestSuccessfulVersionUpgrade:
    """A catalog can be upgraded to a new version."""

    def test_successful_version_upgrade(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            },

            catalog_version="1.0.0",
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
            catalog,

            "2.0.0",
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionResult,
        )
        assert result.updated_catalog.metadata.catalog_version == "2.0.0"
        assert result.version_changed is True


class TestRejectIdenticalVersion:
    """Upgrading to the catalog's current version is rejected."""

    def test_reject_identical_version(self):
        catalog = _build_catalog(
            {},

            catalog_version="1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
                catalog,

                "1.0.0",
            )


class TestUpgradePreservesPolicies:
    """Upgrading preserves every policy in the catalog."""

    def test_upgrade_preserves_policies(self):
        registered_policy = _build_policy(REGISTERED)
        active_policy = _build_policy(ACTIVE)

        catalog = _build_catalog(
            {
                "registered-default": registered_policy,

                "active-default": active_policy,
            },
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
            catalog,

            "2.0.0",
        )

        assert result.updated_catalog.policies["registered-default"] is registered_policy
        assert result.updated_catalog.policies["active-default"] is active_policy


class TestUpgradePreservesOrdering:
    """Upgrading preserves policy ordering."""

    def test_upgrade_preserves_ordering(self):
        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            _build_metadata(),

            [
                ("zeta", _build_policy(REGISTERED)),
                ("alpha", _build_policy(ACTIVE)),
            ],
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
            catalog,

            "2.0.0",
        )

        assert list(result.updated_catalog.policies.keys()) == [
            "zeta",
            "alpha",
        ]


class TestPreviousVersionRecorded:
    """The upgrade result records the catalog exactly as it was before the upgrade."""

    def test_previous_version_recorded(self):
        catalog = _build_catalog(
            {},

            catalog_version="1.0.0",
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
            catalog,

            "2.0.0",
        )

        assert result.previous_catalog is catalog
        assert result.previous_catalog.metadata.catalog_version == "1.0.0"
        assert result.updated_catalog.metadata.catalog_version == "2.0.0"


class TestUpgradeDoesNotMutateOriginalCatalog:
    """Upgrading does not modify the original catalog."""

    def test_upgrade_does_not_mutate_original_catalog(self):
        catalog = _build_catalog(
            {},

            catalog_version="1.0.0",
        )

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
            catalog,

            "2.0.0",
        )

        assert catalog.metadata.catalog_version == "1.0.0"


class TestLatestVersionCheck:
    """A valid catalog is reported as being at its latest version."""

    def test_latest_version_check(self):
        catalog = _build_catalog({})

        assert (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().is_latest(
                catalog
            )
            is True
        )


class TestVersionReturnsCurrentVersion:
    """version() reflects the catalog's current metadata version."""

    def test_version_returns_current_version(self):
        catalog = _build_catalog(
            {},

            catalog_version="3.1.4",
        )

        version = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().version(
            catalog
        )

        assert isinstance(
            version,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersion,
        )
        assert version.version == "3.1.4"
        assert version.previous_version is None
        assert isinstance(version.created_at, datetime)


class TestRejectNoneCatalogOnUpgrade:
    """A None catalog is rejected by upgrade()."""

    def test_reject_none_catalog_on_upgrade(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
                None,

                "2.0.0",
            )


class TestRejectNoneVersionOnUpgrade:
    """A None version is rejected by upgrade()."""

    def test_reject_none_version_on_upgrade(self):
        catalog = _build_catalog({})

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
                catalog,

                None,
            )


class TestRejectEmptyVersionOnUpgrade:
    """An empty version string is rejected by upgrade()."""

    def test_reject_empty_version_on_upgrade(self):
        catalog = _build_catalog({})

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
                catalog,

                "",
            )


class TestRejectNonStringVersionOnUpgrade:
    """A non-string version is rejected by upgrade()."""

    def test_reject_non_string_version_on_upgrade(self):
        catalog = _build_catalog({})

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
                catalog,

                2,
            )


class TestRejectMissingMetadataOnUpgrade:
    """A catalog with missing metadata is rejected by upgrade()."""

    def test_reject_missing_metadata_on_upgrade(self):
        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=None,

            policies={},
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().upgrade(
                catalog,

                "2.0.0",
            )


class TestRejectNoneCatalogOnIsLatest:
    """A None catalog is rejected by is_latest()."""

    def test_reject_none_catalog_on_is_latest(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().is_latest(
                None
            )


class TestRejectNoneCatalogOnVersion:
    """A None catalog is rejected by version()."""

    def test_reject_none_catalog_on_version(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogVersionManager().version(
                None
            )
