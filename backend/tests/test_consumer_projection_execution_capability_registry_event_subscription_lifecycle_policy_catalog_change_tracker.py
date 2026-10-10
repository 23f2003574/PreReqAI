import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeSet,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
)


REGISTERED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED
ACTIVE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE

ADDED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType.ADDED
UPDATED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType.UPDATED
REMOVED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeType.REMOVED


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


class TestIdenticalCatalogs:
    """Tracking identical catalogs reports no changes."""

    def test_identical_catalogs(self):
        policy = _build_policy(REGISTERED)

        previous = _build_catalog(
            {
                "shared": policy,
            }
        )
        current = _build_catalog(
            {
                "shared": policy,
            }
        )

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert isinstance(
            change_set,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeSet,
        )
        assert change_set.added_changes == ()
        assert change_set.updated_changes == ()
        assert change_set.removed_changes == ()
        assert change_set.has_changes is False


class TestAddedPolicies:
    """Policies present only in the current catalog are tracked as added."""

    def test_added_policies(self):
        previous = _build_catalog({})
        current = _build_catalog(
            {
                "new-policy": _build_policy(REGISTERED),
            }
        )

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert len(change_set.added_changes) == 1
        assert change_set.added_changes[0].policy_identifier == "new-policy"
        assert change_set.added_changes[0].change_type == ADDED


class TestUpdatedPolicies:
    """Policies present in both catalogs with different content are tracked as updated."""

    def test_updated_policies(self):
        previous = _build_catalog(
            {
                "conflicting": _build_policy(REGISTERED),
            }
        )
        current = _build_catalog(
            {
                "conflicting": _build_policy(ACTIVE),
            }
        )

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert len(change_set.updated_changes) == 1
        assert change_set.updated_changes[0].policy_identifier == "conflicting"
        assert change_set.updated_changes[0].change_type == UPDATED


class TestRemovedPolicies:
    """Policies present only in the previous catalog are tracked as removed."""

    def test_removed_policies(self):
        previous = _build_catalog(
            {
                "obsolete": _build_policy(REGISTERED),
            }
        )
        current = _build_catalog({})

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert len(change_set.removed_changes) == 1
        assert change_set.removed_changes[0].policy_identifier == "obsolete"
        assert change_set.removed_changes[0].change_type == REMOVED


class TestMixedChanges:
    """Additions, updates, and removals can all be tracked at once."""

    def test_mixed_changes(self):
        previous = _build_catalog(
            {
                "unchanged": _build_policy(REGISTERED),

                "conflicting": _build_policy(REGISTERED),

                "obsolete": _build_policy(REGISTERED),
            }
        )
        current = _build_catalog(
            {
                "unchanged": _build_policy(REGISTERED),

                "conflicting": _build_policy(ACTIVE),

                "new-policy": _build_policy(ACTIVE),
            }
        )

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert [
            change.policy_identifier

            for change in change_set.added_changes
        ] == ["new-policy"]

        assert [
            change.policy_identifier

            for change in change_set.updated_changes
        ] == ["conflicting"]

        assert [
            change.policy_identifier

            for change in change_set.removed_changes
        ] == ["obsolete"]


class TestTotalChangesComputedCorrectly:
    """total_changes equals the sum of added, updated, and removed changes."""

    def test_total_changes_computed_correctly(self):
        previous = _build_catalog(
            {
                "conflicting": _build_policy(REGISTERED),

                "obsolete": _build_policy(REGISTERED),
            }
        )
        current = _build_catalog(
            {
                "conflicting": _build_policy(ACTIVE),

                "new-policy": _build_policy(ACTIVE),
            }
        )

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert change_set.total_changes == 3


class TestHasChangesComputedCorrectly:
    """has_changes is True only when at least one change was detected."""

    def test_has_changes_computed_correctly(self):
        policy = _build_policy(REGISTERED)

        no_change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            _build_catalog(
                {
                    "shared": policy,
                }
            ),

            _build_catalog(
                {
                    "shared": policy,
                }
            ),
        )

        with_change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            _build_catalog({}),

            _build_catalog(
                {
                    "new-policy": policy,
                }
            ),
        )

        assert no_change_set.has_changes is False
        assert with_change_set.has_changes is True


class TestOrderingPreserved:
    """Added and removed changes preserve their respective catalog's ordering."""

    def test_ordering_preserved(self):
        previous = _build_catalog(
            [
                ("removed-zeta", _build_policy(REGISTERED)),
                ("removed-alpha", _build_policy(REGISTERED)),
            ]
        )
        current = _build_catalog(
            [
                ("added-zeta", _build_policy(ACTIVE)),
                ("added-alpha", _build_policy(ACTIVE)),
            ]
        )

        change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
            previous,

            current,
        )

        assert [
            change.policy_identifier

            for change in change_set.added_changes
        ] == [
            "added-zeta",
            "added-alpha",
        ]

        assert [
            change.policy_identifier

            for change in change_set.removed_changes
        ] == [
            "removed-zeta",
            "removed-alpha",
        ]


class TestRejectNonePreviousCatalog:
    """A None previous catalog is rejected."""

    def test_reject_none_previous_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
                None,

                _build_catalog({}),
            )


class TestRejectNoneCurrentCatalog:
    """A None current catalog is rejected."""

    def test_reject_none_current_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
                _build_catalog({}),

                None,
            )


class TestRejectDuplicateIdentifiers:
    """A catalog whose policies structure contains duplicate identifiers is rejected."""

    def test_reject_duplicate_identifiers(self):
        malformed_current = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=_build_metadata(),

            policies=[
                ("duplicate", _build_policy(REGISTERED)),
                ("duplicate", _build_policy(ACTIVE)),
            ],
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
                _build_catalog({}),

                malformed_current,
            )


class TestRejectInvalidCatalogState:
    """A catalog with a None policy value is rejected."""

    def test_reject_invalid_catalog_state(self):
        malformed_previous = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=_build_metadata(),

            policies={
                "broken": None,
            },
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTrackingError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogChangeTracker().track(
                malformed_previous,

                _build_catalog({}),
            )
