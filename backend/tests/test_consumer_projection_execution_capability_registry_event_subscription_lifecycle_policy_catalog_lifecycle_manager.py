import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
)


REGISTERED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED
ACTIVE_SUBSCRIPTION_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE

DRAFT = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DRAFT
ACTIVE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ACTIVE
DEPRECATED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.DEPRECATED
ARCHIVED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleState.ARCHIVED


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            REGISTERED,
            ACTIVE_SUBSCRIPTION_STATE,
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


class TestActivateDraftCatalog:
    """A freshly seen catalog is DRAFT and can be activated."""

    def test_activate_draft_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        result = manager.activate(catalog)

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleResult,
        )
        assert result.previous_state == DRAFT
        assert result.current_state == ACTIVE
        assert manager.state(catalog) == ACTIVE


class TestDeprecateActiveCatalog:
    """An ACTIVE catalog can be deprecated."""

    def test_deprecate_active_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)

        result = manager.deprecate(catalog)

        assert result.previous_state == ACTIVE
        assert result.current_state == DEPRECATED
        assert manager.state(catalog) == DEPRECATED


class TestArchiveActiveCatalog:
    """An ACTIVE catalog can be archived directly."""

    def test_archive_active_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)

        result = manager.archive(catalog)

        assert result.previous_state == ACTIVE
        assert result.current_state == ARCHIVED
        assert manager.state(catalog) == ARCHIVED


class TestArchiveDeprecatedCatalog:
    """A DEPRECATED catalog can be archived."""

    def test_archive_deprecated_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)
        manager.deprecate(catalog)

        result = manager.archive(catalog)

        assert result.previous_state == DEPRECATED
        assert result.current_state == ARCHIVED


class TestRejectInvalidTransitions:
    """Transitions outside the allowed graph are rejected."""

    def test_reject_activate_already_active_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.activate(catalog)

    def test_reject_deprecate_draft_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.deprecate(catalog)

    def test_reject_archive_draft_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.archive(catalog)

    def test_reject_activate_archived_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)
        manager.archive(catalog)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.activate(catalog)

    def test_reject_deprecate_archived_catalog(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)
        manager.archive(catalog)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.deprecate(catalog)


class TestLifecycleStateRetrieval:
    """state() reports a catalog's current lifecycle state."""

    def test_lifecycle_state_retrieval(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        assert manager.state(catalog) == DRAFT

        manager.activate(catalog)

        assert manager.state(catalog) == ACTIVE


class TestPreserveCatalogContents:
    """Lifecycle transitions never alter the catalog's metadata or policies."""

    def test_preserve_catalog_contents(self):
        policy = _build_policy(REGISTERED)

        catalog = _build_catalog(
            {
                "registered-default": policy,
            }
        )

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        result = manager.activate(catalog)

        assert result.catalog is catalog
        assert result.catalog.policies["registered-default"] is policy
        assert result.catalog.metadata is catalog.metadata


class TestImmutableLifecycleUpdates:
    """Lifecycle results cannot have their fields reassigned."""

    def test_immutable_lifecycle_updates(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        result = manager.activate(catalog)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.current_state = DEPRECATED


class TestRejectInvalidInputs:
    """None catalogs and invalid catalog states are rejected."""

    def test_reject_none_catalog_on_activate(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager().activate(
                None
            )

    def test_reject_none_catalog_on_state(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager().state(
                None
            )

    def test_reject_catalog_missing_metadata(self):
        malformed_catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=None,

            policies={},
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager().activate(
                malformed_catalog
            )

    def test_reject_missing_lifecycle_metadata(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager._lifecycle_by_catalog_id[id(catalog)] = None

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.state(catalog)

    def test_reject_invalid_lifecycle_state(self):
        catalog = _build_catalog({})

        manager = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleManager()

        manager.activate(catalog)

        corrupted_lifecycle = dataclasses.replace(
            manager._lifecycle_by_catalog_id[id(catalog)],

            state="active",
        )

        manager._lifecycle_by_catalog_id[id(catalog)] = corrupted_lifecycle

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogLifecycleError
        ):
            manager.state(catalog)
