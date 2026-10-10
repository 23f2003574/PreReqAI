import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionReadinessReport,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
    ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer,
    ResearchWorkspaceConsumerProjectionReadinessTransitionError,
)


READY = ResearchWorkspaceConsumerProjectionReadiness.READY
DEGRADED_READY = ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
BLOCKED_READINESS = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED

ALL_REQUIREMENTS_MET = (
    ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
)
OPTIONAL_CONSTRAINTS_PRESENT = (
    ResearchWorkspaceConsumerProjectionReadinessReason.OPTIONAL_CONSTRAINTS_PRESENT
)
REQUIRED_DEPENDENCY_MISSING = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING
)
EXECUTION_DISABLED = (
    ResearchWorkspaceConsumerProjectionReadinessReason.EXECUTION_DISABLED
)

UNCHANGED = ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
IMPROVED = ResearchWorkspaceConsumerProjectionReadinessTransition.IMPROVED
DEGRADED = ResearchWorkspaceConsumerProjectionReadinessTransition.DEGRADED
BLOCKED_TRANSITION = (
    ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
)
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED


def _make_report(
    *,
    projection_name="workspace.bootstrap",
    readiness=READY,
    reason=ALL_REQUIREMENTS_MET,
    executable=True,
    issues=(),
):
    return ResearchWorkspaceConsumerProjectionReadinessReport(
        projection_name=projection_name,
        readiness=readiness,
        executable=executable,
        reason=reason,
        issues=issues,
    )


class TestTransitionResolution:
    """Test the full readiness transition table."""

    def test_ready_to_ready_is_unchanged(self):
        previous = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)
        current = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == UNCHANGED

    def test_ready_to_degraded_ready_is_degraded(self):
        previous = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)
        current = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == DEGRADED

    def test_ready_to_blocked_is_blocked(self):
        previous = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=EXECUTION_DISABLED,
            executable=False,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == BLOCKED_TRANSITION

    def test_degraded_ready_to_ready_is_recovered(self):
        previous = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )
        current = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == RECOVERED

    def test_degraded_ready_to_blocked_is_blocked(self):
        previous = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == BLOCKED_TRANSITION

    def test_blocked_to_ready_is_recovered(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=EXECUTION_DISABLED,
            executable=False,
        )
        current = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == RECOVERED

    def test_blocked_to_degraded_ready_is_improved(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
        )
        current = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == IMPROVED

    def test_blocked_to_blocked_is_unchanged(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=EXECUTION_DISABLED,
            executable=False,
        )
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == UNCHANGED

    def test_degraded_ready_to_degraded_ready_is_unchanged(self):
        previous = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )
        current = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == UNCHANGED


class TestProjectionMismatch:
    """Comparing reports for different projections is rejected."""

    def test_projection_mismatch_raises_error(self):
        previous = _make_report(projection_name="workspace.bootstrap")
        current = _make_report(projection_name="workspace.attention")

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessTransitionError
        ):
            analyzer.analyze(previous, current)


class TestReasonsPreserved:
    """Both previous and current reasons are kept, not recomputed."""

    def test_reasons_are_preserved(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
        )
        current = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.previous_reason == REQUIRED_DEPENDENCY_MISSING
        assert report.current_reason == OPTIONAL_CONSTRAINTS_PRESENT


class TestChangedProperty:
    """The derived `changed` property mirrors readiness movement."""

    def test_changed_true_when_readiness_differs(self):
        previous = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=EXECUTION_DISABLED,
            executable=False,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.changed is True

    def test_changed_false_when_readiness_is_the_same(self):
        previous = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)
        current = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.changed is False


class TestDeterminism:
    """Analyzing the same pair twice yields equal transition reports."""

    def test_equivalent_inputs_produce_equivalent_reports(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=EXECUTION_DISABLED,
            executable=False,
        )
        current = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )

        first = analyzer.analyze(previous, current)
        second = analyzer.analyze(previous, current)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees of the analyzer."""

    def test_analyzer_has_no_external_dependencies(self):
        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )

        assert analyzer.__dict__ == {}

    def test_analyzer_does_not_mutate_input_reports(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=EXECUTION_DISABLED,
            executable=False,
        )
        current = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        previous_dict = previous.to_dict()
        current_dict = current.to_dict()

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        analyzer.analyze(previous, current)

        assert previous.to_dict() == previous_dict
        assert current.to_dict() == current_dict

    def test_analyzer_works_from_reports_alone(self):
        # No plan, evaluator, or summary object is ever constructed
        # here - proves the analyzer only needs the two reports.
        previous = _make_report(
            projection_name="workspace.attention",
            readiness=READY,
            reason=ALL_REQUIREMENTS_MET,
        )
        current = _make_report(
            projection_name="workspace.attention",
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        analyzer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionAnalyzer()
        )
        report = analyzer.analyze(previous, current)

        assert report.transition == DEGRADED
