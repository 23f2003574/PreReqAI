import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessExplanationError,
    ResearchWorkspaceConsumerProjectionReadinessIssue,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionReadinessReport,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
    ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer,
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


READY = ResearchWorkspaceConsumerProjectionReadiness.READY
DEGRADED_READY = ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
BLOCKED_READINESS = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED

ALL_REQUIREMENTS_MET = (
    ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
)
REQUIRED_DEPENDENCY_MISSING = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING
)
BUDGET_EXHAUSTED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReason.BUDGET_EXHAUSTED
)

UNCHANGED = ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
BLOCKED_TRANSITION = (
    ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
)
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED


def _make_issue(code, message="issue"):
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


def _make_transition(
    *,
    projection_name="workspace.bootstrap",
    previous_readiness=READY,
    current_readiness=READY,
    transition=UNCHANGED,
    previous_reason=ALL_REQUIREMENTS_MET,
    current_reason=ALL_REQUIREMENTS_MET,
):
    return ResearchWorkspaceConsumerProjectionReadinessTransitionReport(
        projection_name=projection_name,
        previous_readiness=previous_readiness,
        current_readiness=current_readiness,
        transition=transition,
        previous_reason=previous_reason,
        current_reason=current_reason,
    )


class TestAppearedIssue:
    """An issue present only in the current report has appeared."""

    def test_appeared_issue_detected(self):
        previous = _make_report(readiness=READY)
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue("missing_dependency"),),
        )
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.appeared_issues == ("missing_dependency",)
        assert explanation.resolved_issues == ()
        assert explanation.persistent_issues == ()


class TestResolvedIssue:
    """An issue present only in the previous report has resolved."""

    def test_resolved_issue_detected(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue("expired_source"),),
        )
        current = _make_report(readiness=READY)
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=READY,
            transition=RECOVERED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.resolved_issues == ("expired_source",)
        assert explanation.appeared_issues == ()
        assert explanation.persistent_issues == ()


class TestPersistentIssue:
    """An issue present in both reports has persisted."""

    def test_persistent_issue_detected(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=BUDGET_EXHAUSTED_REASON,
            executable=False,
            issues=(_make_issue("budget_exhausted"),),
        )
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=BUDGET_EXHAUSTED_REASON,
            executable=False,
            issues=(_make_issue("budget_exhausted"),),
        )
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=BLOCKED_READINESS,
            transition=UNCHANGED,
            previous_reason=BUDGET_EXHAUSTED_REASON,
            current_reason=BUDGET_EXHAUSTED_REASON,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.persistent_issues == ("budget_exhausted",)
        assert explanation.appeared_issues == ()
        assert explanation.resolved_issues == ()


class TestMultipleAppearedIssues:
    """Multiple newly-detected issues all appear, in evaluator order."""

    def test_multiple_appeared_issues(self):
        previous = _make_report(readiness=READY)
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(
                _make_issue("missing_dependency"),
                _make_issue("budget_exhausted"),
            ),
        )
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.appeared_issues == (
            "missing_dependency",
            "budget_exhausted",
        )


class TestMultipleResolvedIssues:
    """Multiple no-longer-present issues all resolve, in evaluator order."""

    def test_multiple_resolved_issues(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(
                _make_issue("missing_dependency"),
                _make_issue("expired_source"),
            ),
        )
        current = _make_report(readiness=READY)
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=READY,
            transition=RECOVERED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.resolved_issues == (
            "missing_dependency",
            "expired_source",
        )


class TestEmptyReports:
    """Two issue-free reports produce an empty explanation."""

    def test_empty_reports_produce_no_changes(self):
        previous = _make_report(readiness=READY)
        current = _make_report(readiness=READY)
        transition = _make_transition()

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.appeared_issues == ()
        assert explanation.resolved_issues == ()
        assert explanation.persistent_issues == ()
        assert explanation.changes == ()


class TestStableOrdering:
    """Codes are ordered by first appearance: previous issues, then
    current issues, each in their own existing evaluator order."""

    def test_recovery_example_orders_persistent_after_resolved_by_report(
        self,
    ):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(
                _make_issue("missing_dependency"),
                _make_issue("expired_source"),
            ),
        )
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue("expired_source"),),
        )
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=BLOCKED_READINESS,
            transition=UNCHANGED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        codes = [change.code for change in explanation.changes]

        assert codes == ["missing_dependency", "expired_source"]
        assert explanation.resolved_issues == ("missing_dependency",)
        assert explanation.persistent_issues == ("expired_source",)

    def test_ordering_is_stable_across_repeated_calls(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue("missing_dependency"),),
        )
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(
                _make_issue("missing_dependency"),
                _make_issue("budget_exhausted"),
            ),
        )
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=BLOCKED_READINESS,
            transition=UNCHANGED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )

        first = explainer.explain(previous, current, transition)
        second = explainer.explain(previous, current, transition)

        assert first.changes == second.changes


class TestProjectionMismatch:
    """Reports/transition describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        previous = _make_report(projection_name="workspace.bootstrap")
        current = _make_report(projection_name="workspace.attention")
        transition = _make_transition(projection_name="workspace.bootstrap")

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessExplanationError
        ):
            explainer.explain(previous, current, transition)


class TestTransitionMismatch:
    """A transition describing different readiness values is rejected."""

    def test_transition_mismatch_raises_error(self):
        previous = _make_report(readiness=READY)
        current = _make_report(readiness=READY)
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessExplanationError
        ):
            explainer.explain(previous, current, transition)


class TestDuplicateIssueCodes:
    """Duplicate codes within one report collapse to a single change."""

    def test_duplicate_codes_in_current_report_collapse(self):
        previous = _make_report(readiness=READY)
        current = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(
                _make_issue("missing_dependency", "cache missing"),
                _make_issue("missing_dependency", "index missing"),
            ),
        )
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explanation = explainer.explain(previous, current, transition)

        assert explanation.appeared_issues == ("missing_dependency",)
        assert len(explanation.changes) == 1


class TestDeterminism:
    """Explaining the same triple twice yields equal explanations."""

    def test_equivalent_inputs_produce_equivalent_explanations(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue("missing_dependency"),),
        )
        current = _make_report(readiness=READY)
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=READY,
            transition=RECOVERED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )

        first = explainer.explain(previous, current, transition)
        second = explainer.explain(previous, current, transition)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_explainer_has_no_external_dependencies(self):
        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )

        assert explainer.__dict__ == {}

    def test_explainer_does_not_mutate_inputs(self):
        previous = _make_report(
            readiness=BLOCKED_READINESS,
            reason=REQUIRED_DEPENDENCY_MISSING,
            executable=False,
            issues=(_make_issue("missing_dependency"),),
        )
        current = _make_report(readiness=READY)
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=READY,
            transition=RECOVERED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )

        previous_dict = previous.to_dict()
        current_dict = current.to_dict()
        transition_dict = transition.to_dict()

        explainer = (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplainer()
        )
        explainer.explain(previous, current, transition)

        assert previous.to_dict() == previous_dict
        assert current.to_dict() == current_dict
        assert transition.to_dict() == transition_dict
