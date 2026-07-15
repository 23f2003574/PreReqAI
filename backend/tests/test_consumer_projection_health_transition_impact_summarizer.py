import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionHealthSignalChange,
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanation,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


def _make_explanation(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    transition=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
    appeared_signals=(),
    resolved_signals=(),
    persistent_signals=(),
    severity_changes=(),
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionExplanation(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        transition=transition,
        appeared_signals=tuple(appeared_signals),
        resolved_signals=tuple(resolved_signals),
        persistent_signals=tuple(persistent_signals),
        severity_changes=tuple(severity_changes),
    )


def _make_severity_change(
    *,
    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED,
    previous_severity,
    current_severity,
):
    return ResearchWorkspaceConsumerProjectionHealthSignalChange(
        code=code,
        previous_severity=previous_severity,
        current_severity=current_severity,
    )


STALE = ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED
EXPIRED = ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT
EXHAUSTED = ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED
SKIPPED = ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED

INFO = ResearchWorkspaceConsumerProjectionQualitySignalSeverity.INFO
WARNING = ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
CRITICAL = ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL

NONE_IMPACT = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NONE
POSITIVE = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.POSITIVE
NEGATIVE = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NEGATIVE
MIXED = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.MIXED


class TestImpactResolution:
    """Test overall impact classification rules."""

    def test_no_signal_changes_produce_none(self):
        explanation = _make_explanation(persistent_signals=[STALE])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == NONE_IMPACT

    def test_resolved_signal_produces_positive(self):
        explanation = _make_explanation(resolved_signals=[STALE])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == POSITIVE

    def test_severity_decrease_produces_positive(self):
        explanation = _make_explanation(
            persistent_signals=[STALE],
            severity_changes=[
                _make_severity_change(
                    code=STALE,
                    previous_severity=CRITICAL,
                    current_severity=WARNING,
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == POSITIVE

    def test_appeared_signal_produces_negative(self):
        explanation = _make_explanation(appeared_signals=[EXPIRED])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == NEGATIVE

    def test_severity_increase_produces_negative(self):
        explanation = _make_explanation(
            persistent_signals=[STALE],
            severity_changes=[
                _make_severity_change(
                    code=STALE,
                    previous_severity=WARNING,
                    current_severity=CRITICAL,
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == NEGATIVE

    def test_positive_and_negative_changes_produce_mixed(self):
        explanation = _make_explanation(
            appeared_signals=[EXHAUSTED],
            resolved_signals=[STALE],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == MIXED

    def test_persistent_signals_alone_produce_none(self):
        explanation = _make_explanation(persistent_signals=[STALE, SKIPPED])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.impact == NONE_IMPACT
        assert summary.appeared_count == 0
        assert summary.resolved_count == 0
        assert summary.persistent_count == 2


class TestCounts:
    """Test signal category and severity direction counts."""

    def test_appeared_count_is_correct(self):
        explanation = _make_explanation(appeared_signals=[EXPIRED, EXHAUSTED])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.appeared_count == 2

    def test_resolved_count_is_correct(self):
        explanation = _make_explanation(resolved_signals=[STALE, SKIPPED])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.resolved_count == 2

    def test_persistent_count_is_correct(self):
        explanation = _make_explanation(persistent_signals=[STALE])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.persistent_count == 1

    def test_severity_increase_count_is_correct(self):
        explanation = _make_explanation(
            persistent_signals=[STALE, EXPIRED],
            severity_changes=[
                _make_severity_change(
                    code=STALE,
                    previous_severity=WARNING,
                    current_severity=CRITICAL,
                ),
                _make_severity_change(
                    code=EXPIRED,
                    previous_severity=INFO,
                    current_severity=WARNING,
                ),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.severity_increase_count == 2
        assert summary.severity_decrease_count == 0

    def test_severity_decrease_count_is_correct(self):
        explanation = _make_explanation(
            persistent_signals=[STALE, EXPIRED],
            severity_changes=[
                _make_severity_change(
                    code=STALE,
                    previous_severity=CRITICAL,
                    current_severity=WARNING,
                ),
                _make_severity_change(
                    code=EXPIRED,
                    previous_severity=WARNING,
                    current_severity=INFO,
                ),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.severity_decrease_count == 2
        assert summary.severity_increase_count == 0

    def test_warning_to_critical_is_increase(self):
        explanation = _make_explanation(
            persistent_signals=[STALE],
            severity_changes=[
                _make_severity_change(
                    code=STALE,
                    previous_severity=WARNING,
                    current_severity=CRITICAL,
                ),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.severity_increase_count == 1
        assert summary.severity_decrease_count == 0

    def test_critical_to_warning_is_decrease(self):
        explanation = _make_explanation(
            persistent_signals=[STALE],
            severity_changes=[
                _make_severity_change(
                    code=STALE,
                    previous_severity=CRITICAL,
                    current_severity=WARNING,
                ),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.severity_decrease_count == 1
        assert summary.severity_increase_count == 0


class TestIdentityPreservation:
    """Test identity/transition fields are reused, not regenerated."""

    def test_identity_fields_are_preserved(self):
        explanation = _make_explanation(
            projection_name="workspace.attention",
            previous_execution_id="req-previous",
            current_execution_id="req-current",
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.projection_name == "workspace.attention"
        assert summary.previous_execution_id == "req-previous"
        assert summary.current_execution_id == "req-current"

    def test_transition_kind_is_preserved(self):
        explanation = _make_explanation(
            transition=ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert (
            summary.transition
            == ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )


class TestChangedSignalCount:
    """Test the derived changed_signal_count property."""

    def test_changed_signal_count_excludes_unchanged_persistent_signals(self):
        explanation = _make_explanation(
            appeared_signals=[EXHAUSTED],
            resolved_signals=[SKIPPED],
            persistent_signals=[STALE, EXPIRED],
            severity_changes=[
                _make_severity_change(
                    code=EXPIRED,
                    previous_severity=WARNING,
                    current_severity=CRITICAL,
                ),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        # 1 appeared + 1 resolved + 1 severity increase = 3.
        # STALE (persistent, unchanged severity) does not contribute.
        assert summary.changed_signal_count == 3


class TestDeterminism:
    """Test summarization is deterministic."""

    def test_equivalent_explanations_produce_equivalent_summaries(self):
        explanation1 = _make_explanation(appeared_signals=[EXPIRED])
        explanation2 = _make_explanation(appeared_signals=[EXPIRED])

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()

        assert summarizer.summarize(explanation1) == summarizer.summarize(
            explanation2
        )


class TestArchitecturalBoundaries:
    """Test structural guarantees of the summarizer."""

    def test_summarizer_has_no_external_dependencies(self):
        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()

        assert summarizer.__dict__ == {}

    def test_summarizer_does_not_mutate_explanation(self):
        explanation = _make_explanation(
            appeared_signals=[EXPIRED], resolved_signals=[STALE]
        )
        original_dict = explanation.to_dict()

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summarizer.summarize(explanation)

        assert explanation.to_dict() == original_dict

    def test_summarizer_works_from_explanation_alone(self):
        # No receipt, quality signal report, or health transition object
        # is ever constructed here - proves the summarizer only needs
        # the explanation.
        explanation = _make_explanation(
            previous_execution_id="explanation-only-previous",
            current_execution_id="explanation-only-current",
            resolved_signals=[STALE],
        )

        summarizer = ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        summary = summarizer.summarize(explanation)

        assert summary.previous_execution_id == "explanation-only-previous"
        assert summary.impact == POSITIVE
