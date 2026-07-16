from backend.session import (
    ResearchWorkspaceConsumerProjectionReadinessImpact,
    ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer,
    ResearchWorkspaceConsumerProjectionReadinessIssueChange,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
    ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation,
)


UNCHANGED = ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
DEGRADED = ResearchWorkspaceConsumerProjectionReadinessTransition.DEGRADED
BLOCKED_TRANSITION = (
    ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
)
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED

NONE_IMPACT = ResearchWorkspaceConsumerProjectionReadinessImpact.NONE
POSITIVE = ResearchWorkspaceConsumerProjectionReadinessImpact.POSITIVE
NEGATIVE = ResearchWorkspaceConsumerProjectionReadinessImpact.NEGATIVE
MIXED_IMPACT = ResearchWorkspaceConsumerProjectionReadinessImpact.MIXED


def _make_change(code, *, previous, current):
    return ResearchWorkspaceConsumerProjectionReadinessIssueChange(
        code=code,
        previous=previous,
        current=current,
    )


def _make_explanation(
    *,
    projection_name="workspace.bootstrap",
    transition=UNCHANGED,
    appeared_issues=(),
    resolved_issues=(),
    persistent_issues=(),
    changes=(),
):
    return ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation(
        projection_name=projection_name,
        transition=transition,
        appeared_issues=appeared_issues,
        resolved_issues=resolved_issues,
        persistent_issues=persistent_issues,
        changes=changes,
    )


class TestNoChanges:
    """No appeared and no resolved issues produce NONE."""

    def test_no_changes_produces_none_impact(self):
        explanation = _make_explanation(
            transition=UNCHANGED,
            persistent_issues=("budget_exhausted",),
            changes=(
                _make_change(
                    "budget_exhausted", previous=True, current=True
                ),
            ),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.impact == NONE_IMPACT


class TestResolvedOnly:
    """Resolved issues with no appearances produce POSITIVE."""

    def test_resolved_only_produces_positive_impact(self):
        explanation = _make_explanation(
            transition=RECOVERED,
            resolved_issues=("missing_dependency",),
            changes=(
                _make_change(
                    "missing_dependency", previous=True, current=False
                ),
            ),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.impact == POSITIVE


class TestAppearedOnly:
    """Appeared issues with no resolutions produce NEGATIVE."""

    def test_appeared_only_produces_negative_impact(self):
        explanation = _make_explanation(
            transition=DEGRADED,
            appeared_issues=("expired_source",),
            changes=(
                _make_change(
                    "expired_source", previous=False, current=True
                ),
            ),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.impact == NEGATIVE


class TestAppearedAndResolved:
    """Both appeared and resolved issues produce MIXED."""

    def test_appeared_and_resolved_produces_mixed_impact(self):
        explanation = _make_explanation(
            transition=BLOCKED_TRANSITION,
            appeared_issues=("budget_exhausted",),
            resolved_issues=("missing_dependency",),
            changes=(
                _make_change(
                    "budget_exhausted", previous=False, current=True
                ),
                _make_change(
                    "missing_dependency", previous=True, current=False
                ),
            ),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.impact == MIXED_IMPACT


class TestCounts:
    """appeared_count/resolved_count/persistent_count are derived correctly."""

    def test_counts_derived_from_explanation(self):
        explanation = _make_explanation(
            appeared_issues=("budget_exhausted", "expired_source"),
            resolved_issues=("missing_dependency",),
            persistent_issues=("projection_disabled",),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.appeared_count == 2
        assert summary.resolved_count == 1
        assert summary.persistent_count == 1
        assert summary.changed_count == 3


class TestPersistentIgnored:
    """Persistent-only issues never influence the impact classification."""

    def test_persistent_issues_do_not_affect_impact(self):
        explanation = _make_explanation(
            transition=UNCHANGED,
            persistent_issues=("budget_exhausted", "expired_source"),
            changes=(
                _make_change(
                    "budget_exhausted", previous=True, current=True
                ),
                _make_change(
                    "expired_source", previous=True, current=True
                ),
            ),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.impact == NONE_IMPACT
        assert summary.persistent_count == 2


class TestStableOutput:
    """Identity fields are copied directly from the explanation."""

    def test_identity_fields_are_preserved(self):
        explanation = _make_explanation(
            projection_name="workspace.attention",
            transition=DEGRADED,
            appeared_issues=("optional_stage_skipped",),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert summary.projection_name == "workspace.attention"
        assert summary.transition == DEGRADED


class TestDeterminism:
    """Summarizing the same explanation twice yields equal summaries."""

    def test_equivalent_explanations_produce_equivalent_summaries(self):
        explanation = _make_explanation(
            transition=BLOCKED_TRANSITION,
            appeared_issues=("budget_exhausted",),
            resolved_issues=("missing_dependency",),
        )

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )

        first = summarizer.summarize(explanation)
        second = summarizer.summarize(explanation)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_summarizer_has_no_external_dependencies(self):
        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )

        assert summarizer.__dict__ == {}

    def test_summarizer_does_not_mutate_explanation(self):
        explanation = _make_explanation(
            transition=BLOCKED_TRANSITION,
            appeared_issues=("budget_exhausted",),
            resolved_issues=("missing_dependency",),
        )

        explanation_dict_before = explanation.to_dict()

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summarizer.summarize(explanation)

        assert explanation.to_dict() == explanation_dict_before

    def test_summary_carries_no_recommendation_or_score(self):
        explanation = _make_explanation()

        summarizer = (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer()
        )
        summary = summarizer.summarize(explanation)

        assert set(summary.to_dict().keys()) == {
            "projection_name",
            "transition",
            "impact",
            "appeared_count",
            "resolved_count",
            "persistent_count",
            "changed_count",
        }
