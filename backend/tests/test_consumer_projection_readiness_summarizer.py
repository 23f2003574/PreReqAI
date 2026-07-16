from backend.session import (
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessIssue,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionReadinessReport,
    ResearchWorkspaceConsumerProjectionReadinessSummarizer,
)


READY = ResearchWorkspaceConsumerProjectionReadiness.READY
DEGRADED_READY = ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
BLOCKED = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED

ALL_REQUIREMENTS_MET = (
    ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
)
OPTIONAL_CONSTRAINTS_PRESENT = (
    ResearchWorkspaceConsumerProjectionReadinessReason.OPTIONAL_CONSTRAINTS_PRESENT
)
REQUIRED_DEPENDENCY_MISSING = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING
)


def _make_issue(code="missing_dependency", message="missing"):
    return ResearchWorkspaceConsumerProjectionReadinessIssue(
        code=code,
        message=message,
    )


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


class TestReadySummary:
    """A READY report summarizes with no issues and healthy=True."""

    def test_ready_report_summarized_correctly(self):
        report = _make_report(
            readiness=READY,
            reason=ALL_REQUIREMENTS_MET,
            executable=True,
            issues=(),
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.projection_name == "workspace.bootstrap"
        assert summary.readiness == READY
        assert summary.reason == ALL_REQUIREMENTS_MET
        assert summary.issue_count == 0
        assert summary.executable is True
        assert summary.healthy is True


class TestDegradedSummary:
    """A DEGRADED_READY report summarizes as executable but not healthy."""

    def test_degraded_report_summarized_correctly(self):
        report = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
            executable=True,
            issues=(
                _make_issue("optional_stage_skipped", "skipped 1"),
                _make_issue("degraded_dependency", "degraded 1"),
            ),
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.readiness == DEGRADED_READY
        assert summary.reason == OPTIONAL_CONSTRAINTS_PRESENT
        assert summary.issue_count == 2
        assert summary.executable is True
        assert summary.healthy is False


class TestBlockedSummary:
    """A BLOCKED report summarizes as not executable and not healthy."""

    def test_blocked_report_summarized_correctly(self):
        report = _make_report(
            readiness=BLOCKED,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(
                _make_issue("missing_dependency", "missing 1"),
                _make_issue("expired_source", "expired 1"),
                _make_issue("budget_exhausted", "exhausted"),
            ),
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.readiness == BLOCKED
        assert summary.reason == REQUIRED_DEPENDENCY_MISSING
        assert summary.issue_count == 3
        assert summary.executable is False
        assert summary.healthy is False


class TestIssueCountDerivation:
    """issue_count always equals len(report.issues)."""

    def test_issue_count_matches_report_issue_length(self):
        report = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
            issues=(
                _make_issue("optional_stage_skipped", "a"),
                _make_issue("stale_usable_source", "b"),
                _make_issue("degraded_dependency", "c"),
            ),
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.issue_count == len(report.issues) == 3


class TestHealthyProperty:
    """`healthy` is true only for READY."""

    def test_healthy_true_for_ready(self):
        report = _make_report(readiness=READY, reason=ALL_REQUIREMENTS_MET)

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.healthy is True

    def test_healthy_false_for_degraded_ready(self):
        report = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.healthy is False

    def test_healthy_false_for_blocked(self):
        report = _make_report(
            readiness=BLOCKED,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.healthy is False


class TestIdentityPreservation:
    """projection_name, readiness, reason, executable are copied, not recomputed."""

    def test_identity_fields_are_preserved(self):
        report = _make_report(
            projection_name="workspace.attention",
            readiness=BLOCKED,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue(),),
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.projection_name == "workspace.attention"
        assert summary.readiness == report.readiness
        assert summary.reason == report.reason
        assert summary.executable == report.executable


class TestDeterminism:
    """Summarizing the same report twice yields equal summaries."""

    def test_equivalent_reports_produce_equivalent_summaries(self):
        report = _make_report(
            readiness=DEGRADED_READY,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
            issues=(_make_issue(),),
        )

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()

        first = summarizer.summarize(report)
        second = summarizer.summarize(report)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_summarizer_has_no_external_dependencies(self):
        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()

        assert summarizer.__dict__ == {}

    def test_summarizer_does_not_mutate_report(self):
        report = _make_report(
            readiness=BLOCKED,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue(),),
        )

        report_dict_before = report.to_dict()

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summarizer.summarize(report)

        assert report.to_dict() == report_dict_before

    def test_summary_carries_no_execution_outcome(self):
        # The summary is a pure aggregation: it exposes no execution
        # result, output, receipt, recommendation, or score.
        report = _make_report()

        summarizer = ResearchWorkspaceConsumerProjectionReadinessSummarizer()
        summary = summarizer.summarize(report)

        assert set(summary.to_dict().keys()) == {
            "projection_name",
            "readiness",
            "reason",
            "issue_count",
            "executable",
            "healthy",
        }
