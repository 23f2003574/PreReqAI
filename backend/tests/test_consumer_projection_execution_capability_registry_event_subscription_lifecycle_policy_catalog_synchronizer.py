import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer,
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


def _build_catalog(policies):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
        _build_metadata(),

        policies,
    )


REGISTERED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED
ACTIVE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE

PREFER_SOURCE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy.PREFER_SOURCE
PREFER_TARGET = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy.PREFER_TARGET
FAIL_ON_CONFLICT = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationStrategy.FAIL_ON_CONFLICT


class TestSynchronizeIdenticalCatalogs:
    """Synchronizing identical catalogs reports no changes."""

    def test_synchronize_identical_catalogs(self):
        policy = _build_policy(REGISTERED)

        source = _build_catalog(
            {
                "shared": policy,
            }
        )
        target = _build_catalog(
            {
                "shared": policy,
            }
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationResult,
        )
        assert result.added_policy_identifiers == ()
        assert result.updated_policy_identifiers == ()
        assert result.removed_policy_identifiers == ()
        assert result.has_changes is False
        assert list(result.synchronized_catalog.policies.keys()) == ["shared"]


class TestAddNewPolicies:
    """Policies present only in the source catalog are added."""

    def test_add_new_policies(self):
        source = _build_catalog(
            {
                "new-policy": _build_policy(REGISTERED),
            }
        )
        target = _build_catalog({})

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert result.added_policy_identifiers == ("new-policy",)
        assert result.has_changes is True
        assert "new-policy" in result.synchronized_catalog.policies


class TestUpdateExistingPolicies:
    """Conflicting policies present in both catalogs are reported as updated."""

    def test_update_existing_policies(self):
        source = _build_catalog(
            {
                "conflicting": _build_policy(ACTIVE),
            }
        )
        target = _build_catalog(
            {
                "conflicting": _build_policy(REGISTERED),
            }
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert result.updated_policy_identifiers == ("conflicting",)
        assert result.has_changes is True


class TestRemoveObsoletePolicies:
    """Policies present only in the target catalog are removed."""

    def test_remove_obsolete_policies(self):
        source = _build_catalog({})
        target = _build_catalog(
            {
                "obsolete": _build_policy(REGISTERED),
            }
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert result.removed_policy_identifiers == ("obsolete",)
        assert result.has_changes is True
        assert "obsolete" not in result.synchronized_catalog.policies


class TestPreferSourceStrategy:
    """PREFER_SOURCE resolves conflicts using the source catalog's policy."""

    def test_prefer_source_strategy(self):
        source_policy = _build_policy(ACTIVE)
        target_policy = _build_policy(REGISTERED)

        source = _build_catalog(
            {
                "conflicting": source_policy,
            }
        )
        target = _build_catalog(
            {
                "conflicting": target_policy,
            }
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert result.synchronized_catalog.policies["conflicting"] is source_policy


class TestPreferTargetStrategy:
    """PREFER_TARGET resolves conflicts using the target catalog's policy."""

    def test_prefer_target_strategy(self):
        source_policy = _build_policy(ACTIVE)
        target_policy = _build_policy(REGISTERED)

        source = _build_catalog(
            {
                "conflicting": source_policy,
            }
        )
        target = _build_catalog(
            {
                "conflicting": target_policy,
            }
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_TARGET,
        )

        assert result.synchronized_catalog.policies["conflicting"] is target_policy


class TestFailOnConflict:
    """FAIL_ON_CONFLICT raises when the catalogs disagree on a policy."""

    def test_fail_on_conflict(self):
        source = _build_catalog(
            {
                "conflicting": _build_policy(ACTIVE),
            }
        )
        target = _build_catalog(
            {
                "conflicting": _build_policy(REGISTERED),
            }
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
                source,

                target,

                FAIL_ON_CONFLICT,
            )


class TestFailOnConflictAllowsNonConflictingSynchronization:
    """FAIL_ON_CONFLICT does not raise when there is no conflict."""

    def test_fail_on_conflict_allows_non_conflicting_synchronization(self):
        policy = _build_policy(REGISTERED)

        source = _build_catalog(
            {
                "shared": policy,

                "new-policy": _build_policy(ACTIVE),
            }
        )
        target = _build_catalog(
            {
                "shared": policy,
            }
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            FAIL_ON_CONFLICT,
        )

        assert result.added_policy_identifiers == ("new-policy",)


class TestPreservesOrdering:
    """The synchronized catalog preserves target ordering, then appends additions in source order."""

    def test_preserves_ordering(self):
        source = _build_catalog(
            [
                ("kept-a", _build_policy(REGISTERED)),
                ("kept-b", _build_policy(ACTIVE)),
                ("added-z", _build_policy(REGISTERED)),
                ("added-a", _build_policy(ACTIVE)),
            ]
        )
        target = _build_catalog(
            [
                ("kept-b", _build_policy(ACTIVE)),
                ("kept-a", _build_policy(REGISTERED)),
                ("removed", _build_policy(REGISTERED)),
            ]
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert list(result.synchronized_catalog.policies.keys()) == [
            "kept-b",
            "kept-a",
            "added-z",
            "added-a",
        ]


class TestOriginalCatalogsRemainUnchanged:
    """Synchronizing does not mutate either input catalog."""

    def test_original_catalogs_remain_unchanged(self):
        source = _build_catalog(
            {
                "new-policy": _build_policy(ACTIVE),
            }
        )
        target = _build_catalog(
            {
                "obsolete": _build_policy(REGISTERED),
            }
        )

        source_identifiers_before = tuple(source.policies.keys())
        target_identifiers_before = tuple(target.policies.keys())

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
            source,

            target,

            PREFER_SOURCE,
        )

        assert tuple(source.policies.keys()) == source_identifiers_before
        assert tuple(target.policies.keys()) == target_identifiers_before
        assert "new-policy" in source.policies
        assert "obsolete" in target.policies


class TestRejectNoneSourceCatalog:
    """A None source catalog is rejected."""

    def test_reject_none_source_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
                None,

                _build_catalog({}),

                PREFER_SOURCE,
            )


class TestRejectNoneTargetCatalog:
    """A None target catalog is rejected."""

    def test_reject_none_target_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
                _build_catalog({}),

                None,

                PREFER_SOURCE,
            )


class TestRejectNoneStrategy:
    """A None strategy is rejected."""

    def test_reject_none_strategy(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
                _build_catalog({}),

                _build_catalog({}),

                None,
            )


class TestRejectInvalidStrategy:
    """An unrecognized strategy value is rejected."""

    def test_reject_invalid_strategy(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
                _build_catalog({}),

                _build_catalog({}),

                "prefer_source",
            )


class TestRejectDuplicateIdentifiers:
    """A catalog whose policies structure contains duplicate identifiers is rejected."""

    def test_reject_duplicate_identifiers(self):
        malformed_target = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=_build_metadata(),

            policies=[
                ("duplicate", _build_policy(REGISTERED)),
                ("duplicate", _build_policy(ACTIVE)),
            ],
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSynchronizer().synchronize(
                _build_catalog({}),

                malformed_target,

                PREFER_SOURCE,
            )
