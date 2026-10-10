import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW
REJECT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    executable=True,
    title="Capability Accepted",
    message="Projection satisfies all execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage(
        projection_name=projection_name,
        decision=decision,
        executable=executable,
        title=title,
        message=message,
    )


class TestEmptyRegistry:
    """An empty registry produces an all-zero health report."""

    def test_empty_registry(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()

        report = analyzer.analyze(registry)

        assert report.total_projections == 0
        assert report.executable_projections == 0
        assert report.non_executable_projections == 0
        assert report.accepted_projections == 0
        assert report.review_projections == 0
        assert report.rejected_projections == 0


class TestSingleAcceptPackage:
    """A single ACCEPT, executable package is reflected in the counts."""

    def test_single_accept_package(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(decision=ACCEPT, executable=True))

        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()
        report = analyzer.analyze(registry)

        assert report.total_projections == 1
        assert report.executable_projections == 1
        assert report.non_executable_projections == 0
        assert report.accepted_projections == 1
        assert report.review_projections == 0
        assert report.rejected_projections == 0


class TestMixedPackages:
    """Mixed ACCEPT/REVIEW/REJECT packages produce accurate aggregate counts."""

    def test_mixed_decision_packages(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(
            _make_package(
                projection_name="workspace.bootstrap",
                decision=ACCEPT,
                executable=True,
            )
        )
        registry.register(
            _make_package(
                projection_name="workspace.attention",
                decision=REVIEW,
                executable=False,
                title="Capability Requires Review",
                message="Projection requires manual review before execution.",
            )
        )
        registry.register(
            _make_package(
                projection_name="session.actions",
                decision=REJECT,
                executable=False,
                title="Capability Rejected",
                message="Projection does not satisfy execution capability requirements.",
            )
        )

        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()
        report = analyzer.analyze(registry)

        assert report.total_projections == 3
        assert report.executable_projections == 1
        assert report.non_executable_projections == 2
        assert report.accepted_projections == 1
        assert report.review_projections == 1
        assert report.rejected_projections == 1


class TestInvalidRegistry:
    """A None or non-registry value is rejected."""

    def test_reject_none_registry(self):
        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError
        ):
            analyzer.analyze(None)

    def test_reject_non_registry_object(self):
        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError
        ):
            analyzer.analyze(object())


class TestMalformedEntry:
    """An entry that cannot be inspected raises rather than being counted."""

    def test_malformed_entry_raises_error(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry._packages["workspace.bootstrap"] = "not-a-package"

        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError
        ):
            analyzer.analyze(registry)


class TestRegistryUnchanged:
    """Analysis never mutates the registry or its packages."""

    def test_registry_remains_unchanged(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)
        package_dict = package.to_dict()

        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()
        analyzer.analyze(registry)

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert package.to_dict() == package_dict


class TestDeterminism:
    """Analyzing the same registry state twice agrees."""

    def test_repeated_analysis_is_deterministic(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        analyzer = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalyzer()

        first = analyzer.analyze(registry)
        second = analyzer.analyze(registry)

        assert first == second
