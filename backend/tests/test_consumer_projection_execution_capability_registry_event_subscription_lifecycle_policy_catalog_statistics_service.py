from datetime import datetime

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService,
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


class TestEmptyCatalog:
    """An empty catalog reports zeroed, empty statistics."""

    def test_empty_catalog(self):
        report = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            _build_catalog({})
        )

        assert isinstance(
            report,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsReport,
        )
        assert report.statistics.total_policies == 0
        assert report.statistics.unique_policy_identifiers == 0
        assert report.statistics.first_policy_identifier is None
        assert report.statistics.last_policy_identifier is None
        assert report.statistics.empty_catalog is True


class TestSinglePolicy:
    """A catalog with one policy reports matching first and last identifiers."""

    def test_single_policy(self):
        catalog = _build_catalog(
            {
                "solo": _build_policy(REGISTERED),
            }
        )

        report = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            catalog
        )

        assert report.statistics.total_policies == 1
        assert report.statistics.first_policy_identifier == "solo"
        assert report.statistics.last_policy_identifier == "solo"
        assert report.statistics.empty_catalog is False


class TestMultiplePolicies:
    """A catalog with multiple policies reports the correct total."""

    def test_multiple_policies(self):
        catalog = _build_catalog(
            [
                ("zeta", _build_policy(REGISTERED)),
                ("alpha", _build_policy(ACTIVE)),
                ("mid", _build_policy(REGISTERED)),
            ]
        )

        report = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            catalog
        )

        assert report.statistics.total_policies == 3
        assert report.statistics.empty_catalog is False


class TestFirstLastIdentifierCorrect:
    """First and last identifiers follow catalog ordering."""

    def test_first_last_identifier_correct(self):
        catalog = _build_catalog(
            [
                ("zeta", _build_policy(REGISTERED)),
                ("alpha", _build_policy(ACTIVE)),
                ("mid", _build_policy(REGISTERED)),
            ]
        )

        report = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            catalog
        )

        assert report.statistics.first_policy_identifier == "zeta"
        assert report.statistics.last_policy_identifier == "mid"


class TestUniqueCountCorrect:
    """The unique identifier count matches the number of distinct identifiers."""

    def test_unique_count_correct(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),

                "active-default": _build_policy(ACTIVE),
            }
        )

        report = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            catalog
        )

        assert report.statistics.unique_policy_identifiers == 2


class TestGeneratedReport:
    """The report carries a generation timestamp alongside its statistics."""

    def test_generated_report(self):
        catalog = _build_catalog(
            {
                "solo": _build_policy(REGISTERED),
            }
        )

        report = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            catalog
        )

        assert isinstance(
            report.statistics,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatistics,
        )
        assert isinstance(report.generated_at, datetime)


class TestCatalogNotMutated:
    """Generating statistics does not mutate the catalog."""

    def test_catalog_not_mutated(self):
        catalog = _build_catalog(
            [
                ("zeta", _build_policy(REGISTERED)),
                ("alpha", _build_policy(ACTIVE)),
            ]
        )

        identifiers_before = tuple(catalog.policies.keys())

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
            catalog
        )

        assert tuple(catalog.policies.keys()) == identifiers_before


class TestRejectNoneCatalog:
    """A None catalog is rejected."""

    def test_reject_none_catalog(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogStatisticsService().generate(
                None
            )
