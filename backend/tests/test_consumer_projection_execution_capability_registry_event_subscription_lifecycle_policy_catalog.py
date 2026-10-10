import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
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


class TestBuildEmptyCatalog:
    """A catalog with no policies can be built."""

    def test_build_empty_catalog(self):
        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            _build_metadata(),

            {},
        )

        assert isinstance(
            catalog,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
        )
        assert len(catalog.policies) == 0


class TestBuildPopulatedCatalog:
    """A catalog with multiple policies can be built."""

    def test_build_populated_catalog(self):
        registered_policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )
        active_policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            _build_metadata(),

            {
                "registered-default": registered_policy,

                "active-default": active_policy,
            },
        )

        assert len(catalog.policies) == 2
        assert catalog.policies["registered-default"] is registered_policy
        assert catalog.policies["active-default"] is active_policy


class TestCatalogPreservesOrdering:
    """A catalog's policies preserve insertion order."""

    def test_catalog_preserves_ordering(self):
        policy_a = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )
        policy_b = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )
        policy_c = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
        )

        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            _build_metadata(),

            [
                ("zeta", policy_a),
                ("alpha", policy_b),
                ("mid", policy_c),
            ],
        )

        assert list(catalog.policies.keys()) == [
            "zeta",
            "alpha",
            "mid",
        ]


class TestRejectNoneMetadata:
    """None metadata is rejected."""

    def test_reject_none_metadata(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                None,

                {},
            )


class TestRejectNonePolicies:
    """None policies is rejected."""

    def test_reject_none_policies(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                _build_metadata(),

                None,
            )


class TestRejectNonePolicyValue:
    """A None policy value is rejected."""

    def test_reject_none_policy_value(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                _build_metadata(),

                {
                    "broken": None,
                },
            )


class TestRejectEmptyIdentifier:
    """An empty policy identifier is rejected."""

    def test_reject_empty_identifier(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                _build_metadata(),

                {
                    "": _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                    ),
                },
            )


class TestRejectDuplicateIdentifier:
    """A duplicate policy identifier is rejected."""

    def test_reject_duplicate_identifier(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
                _build_metadata(),

                [
                    (
                        "duplicate",
                        _build_policy(
                            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                        ),
                    ),
                    (
                        "duplicate",
                        _build_policy(
                            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
                        ),
                    ),
                ],
            )


class TestImmutableCatalog:
    """A built catalog cannot have its fields reassigned or its policies mutated."""

    def test_immutable_catalog(self):
        catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            _build_metadata(),

            {
                "registered-default": _build_policy(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                ),
            },
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            catalog.metadata = _build_metadata()

        with pytest.raises(TypeError):
            catalog.policies["new-identifier"] = _build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            )
