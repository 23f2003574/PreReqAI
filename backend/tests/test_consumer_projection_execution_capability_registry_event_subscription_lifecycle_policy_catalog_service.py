import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogService,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ),
        initial_state,
    )


def _build_metadata():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
        catalog_name="core-lifecycle-policies",

        catalog_version="1.0.0",

        description="Core lifecycle policy catalog.",
    )


def _build_service(policies):
    catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
        _build_metadata(),

        policies,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogService(
        catalog
    )


class TestContainsExistingPolicy:
    """contains() reports True for a registered identifier."""

    def test_contains_existing_policy(self):
        service = _build_service(
            {
                "registered-default": _build_policy(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                ),
            }
        )

        assert service.contains("registered-default") is True


class TestContainsMissingPolicy:
    """contains() reports False for an unregistered identifier."""

    def test_contains_missing_policy(self):
        service = _build_service({})

        assert service.contains("missing") is False


class TestFindExistingPolicy:
    """find() returns the policy registered under an identifier."""

    def test_find_existing_policy(self):
        policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )

        service = _build_service(
            {
                "registered-default": policy,
            }
        )

        assert service.find("registered-default") is policy


class TestFindMissingPolicy:
    """find() returns None for an unregistered identifier."""

    def test_find_missing_policy(self):
        service = _build_service({})

        assert service.find("missing") is None


class TestListPreservesOrder:
    """list() returns every policy in catalog order."""

    def test_list_preserves_order(self):
        policy_a = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )
        policy_b = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        service = _build_service(
            [
                ("zeta", policy_a),
                ("alpha", policy_b),
            ]
        )

        assert service.list() == (
            policy_a,
            policy_b,
        )


class TestIdentifiersPreserveOrder:
    """identifiers() returns every identifier in catalog order."""

    def test_identifiers_preserve_order(self):
        service = _build_service(
            [
                (
                    "zeta",
                    _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                    ),
                ),
                (
                    "alpha",
                    _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
                    ),
                ),
            ]
        )

        assert service.identifiers() == (
            "zeta",
            "alpha",
        )


class TestIdentifiersReturnsImmutableCollection:
    """identifiers() returns an immutable collection."""

    def test_identifiers_returns_immutable_collection(self):
        service = _build_service({})

        assert isinstance(service.identifiers(), tuple)


class TestListReturnsImmutableCollection:
    """list() returns an immutable collection."""

    def test_list_returns_immutable_collection(self):
        service = _build_service({})

        assert isinstance(service.list(), tuple)


class TestMetadataReturnsCatalogMetadata:
    """metadata() returns the catalog's metadata."""

    def test_metadata_returns_catalog_metadata(self):
        metadata = _build_metadata()

        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            metadata,

            {},
        )

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogService(
            catalog
        )

        assert service.metadata() is metadata


class TestRejectNoneCatalog:
    """The service rejects a None catalog."""

    def test_reject_none_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogService(
                None
            )
