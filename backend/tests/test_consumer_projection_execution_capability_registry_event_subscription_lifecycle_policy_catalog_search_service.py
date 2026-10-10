import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService,
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


def _sample_catalog():
    return _build_catalog(
        [
            ("consumer-alpha", _build_policy(REGISTERED)),
            ("consumer-beta", _build_policy(ACTIVE)),
            ("producer-alpha", _build_policy(REGISTERED)),
            ("producer-gamma", _build_policy(ACTIVE)),
        ]
    )


class TestSearchEmptyCatalog:
    """Searching an empty catalog returns no matches."""

    def test_search_empty_catalog(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _build_catalog({}),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(),
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchResult,
        )
        assert result.total_matches == 0
        assert len(result.matched_policies) == 0


class TestNoMatches:
    """Criteria matching nothing returns an empty result."""

    def test_no_matches(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                identifier_prefix="nonexistent-",
            ),
        )

        assert result.total_matches == 0


class TestExactIdentifierMatch:
    """An include filter with a single identifier matches exactly that policy."""

    def test_exact_identifier_match(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                include_identifiers=("consumer-beta",),
            ),
        )

        assert list(result.matched_policies.keys()) == ["consumer-beta"]
        assert result.total_matches == 1


class TestPrefixSearch:
    """A prefix filter matches only identifiers starting with it."""

    def test_prefix_search(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                identifier_prefix="producer-",
            ),
        )

        assert list(result.matched_policies.keys()) == [
            "producer-alpha",
            "producer-gamma",
        ]


class TestContainsSearch:
    """A substring filter matches identifiers containing it anywhere."""

    def test_contains_search(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                identifier_contains="alpha",
            ),
        )

        assert list(result.matched_policies.keys()) == [
            "consumer-alpha",
            "producer-alpha",
        ]


class TestIncludeFilter:
    """An include filter restricts matches to the given identifiers."""

    def test_include_filter(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                include_identifiers=(
                    "consumer-alpha",
                    "producer-gamma",
                ),
            ),
        )

        assert list(result.matched_policies.keys()) == [
            "consumer-alpha",
            "producer-gamma",
        ]


class TestExcludeFilter:
    """An exclude filter removes the given identifiers from matches."""

    def test_exclude_filter(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                exclude_identifiers=("consumer-alpha",),
            ),
        )

        assert "consumer-alpha" not in result.matched_policies
        assert result.total_matches == 3


class TestCombinedFilters:
    """Multiple filters combine as a logical AND."""

    def test_combined_filters(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                identifier_prefix="consumer-",

                identifier_contains="beta",

                exclude_identifiers=("consumer-gamma",),
            ),
        )

        assert list(result.matched_policies.keys()) == ["consumer-beta"]


class TestOrderingPreserved:
    """Matches are returned in catalog order regardless of filter values."""

    def test_ordering_preserved(self):
        catalog = _build_catalog(
            [
                ("zeta", _build_policy(REGISTERED)),
                ("alpha", _build_policy(ACTIVE)),
                ("mid", _build_policy(REGISTERED)),
            ]
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            catalog,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                include_identifiers=(
                    "alpha",
                    "zeta",
                    "mid",
                ),
            ),
        )

        assert list(result.matched_policies.keys()) == [
            "zeta",
            "alpha",
            "mid",
        ]


class TestImmutableResult:
    """The matched policies mapping cannot be mutated."""

    def test_immutable_result(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
            _sample_catalog(),

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(),
        )

        with pytest.raises(TypeError):
            result.matched_policies["new-identifier"] = _build_policy(REGISTERED)


class TestRejectNoneCatalog:
    """A None catalog is rejected."""

    def test_reject_none_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
                None,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(),
            )


class TestRejectNoneCriteria:
    """None criteria is rejected."""

    def test_reject_none_criteria(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchService().search(
                _sample_catalog(),

                None,
            )


class TestRejectBlankPrefix:
    """A blank identifier prefix is rejected."""

    def test_reject_blank_prefix(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                identifier_prefix="",
            )


class TestRejectBlankContains:
    """A blank identifier substring is rejected."""

    def test_reject_blank_contains(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                identifier_contains="",
            )


class TestRejectBlankIncludeIdentifier:
    """A blank identifier within include_identifiers is rejected."""

    def test_reject_blank_include_identifier(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                include_identifiers=("", "consumer-alpha"),
            )


class TestRejectBlankExcludeIdentifier:
    """A blank identifier within exclude_identifiers is rejected."""

    def test_reject_blank_exclude_identifier(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                exclude_identifiers=("", "consumer-alpha"),
            )


class TestRejectDuplicateIncludeIdentifiers:
    """Duplicate identifiers within include_identifiers are rejected."""

    def test_reject_duplicate_include_identifiers(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                include_identifiers=(
                    "consumer-alpha",
                    "consumer-alpha",
                ),
            )


class TestRejectDuplicateExcludeIdentifiers:
    """Duplicate identifiers within exclude_identifiers are rejected."""

    def test_reject_duplicate_exclude_identifiers(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogSearchCriteria(
                exclude_identifiers=(
                    "consumer-alpha",
                    "consumer-alpha",
                ),
            )
