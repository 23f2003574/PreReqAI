import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
    ResearchWorkspaceConsumerProjectionHealthTransitionExplainer,
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionQualitySignal,
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
    ResearchWorkspaceConsumerProjectionQualitySignalReport,
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


def _make_signal(
    *,
    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED,
    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING,
    value=None,
    message="notable condition",
):
    return ResearchWorkspaceConsumerProjectionQualitySignal(
        code=code,
        severity=severity,
        message=message,
        value=value,
    )


def _make_report(
    *,
    execution_id="exec-1",
    projection_name="workspace.bootstrap",
    signals=(),
):
    has_warnings = any(
        signal.severity
        == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
        for signal in signals
    )
    has_critical_signals = any(
        signal.severity
        == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL
        for signal in signals
    )

    return ResearchWorkspaceConsumerProjectionQualitySignalReport(
        execution_id=execution_id,
        projection_name=projection_name,
        signals=tuple(signals),
        has_warnings=has_warnings,
        has_critical_signals=has_critical_signals,
    )


def _make_transition(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-1",
    previous_health=ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY,
    current_health=ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY,
    kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
):
    return ResearchWorkspaceConsumerProjectionExecutionHealthTransition(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        previous_health=previous_health,
        current_health=current_health,
        kind=kind,
    )


DEGRADED = ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED
STALE = ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED
EXPIRED = ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT
UNKNOWN = ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT
EXHAUSTED = ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED
SKIPPED = ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED
UNCOVERED = ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE

WARNING = ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
CRITICAL_SEVERITY = ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL


class TestSignalDetection:
    """Test appeared/resolved/persistent classification."""

    def test_newly_appearing_signal_is_detected(self):
        previous_report = _make_report(signals=[])
        current_report = _make_report(
            signals=[_make_signal(code=STALE)]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.DETERIORATED
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.appeared_signals == (STALE,)
        assert explanation.resolved_signals == ()
        assert explanation.persistent_signals == ()

    def test_resolved_signal_is_detected(self):
        previous_report = _make_report(
            signals=[_make_signal(code=SKIPPED)]
        )
        current_report = _make_report(signals=[])
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.RECOVERED
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.resolved_signals == (SKIPPED,)
        assert explanation.appeared_signals == ()
        assert explanation.persistent_signals == ()

    def test_persistent_signal_is_detected(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        transition = _make_transition()

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.persistent_signals == (STALE,)
        assert explanation.appeared_signals == ()
        assert explanation.resolved_signals == ()
        assert explanation.severity_changes == ()

    def test_multiple_appeared_signals_are_detected(self):
        previous_report = _make_report(signals=[])
        current_report = _make_report(
            signals=[
                _make_signal(code=EXPIRED, severity=CRITICAL_SEVERITY),
                _make_signal(code=UNKNOWN, severity=WARNING),
            ]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.appeared_signals == (EXPIRED, UNKNOWN)

    def test_multiple_resolved_signals_are_detected(self):
        previous_report = _make_report(
            signals=[
                _make_signal(code=STALE, severity=WARNING),
                _make_signal(code=SKIPPED, severity=WARNING),
            ]
        )
        current_report = _make_report(signals=[])
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.RECOVERED
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.resolved_signals == (STALE, SKIPPED)


class TestSeverityChanges:
    """Test per-code severity comparison."""

    def test_severity_increase_is_detected(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=STALE, severity=CRITICAL_SEVERITY)]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert len(explanation.severity_changes) == 1
        change = explanation.severity_changes[0]
        assert change.code == STALE
        assert change.previous_severity == WARNING
        assert change.current_severity == CRITICAL_SEVERITY
        assert change.severity_changed is True

    def test_severity_decrease_is_detected(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=CRITICAL_SEVERITY)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.IMPROVED
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert len(explanation.severity_changes) == 1
        change = explanation.severity_changes[0]
        assert change.previous_severity == CRITICAL_SEVERITY
        assert change.current_severity == WARNING

    def test_same_severity_does_not_create_severity_change(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        transition = _make_transition()

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.severity_changes == ()

    def test_signal_comparison_uses_code_rather_than_message(self):
        previous_report = _make_report(
            signals=[
                _make_signal(
                    code=STALE,
                    severity=WARNING,
                    message="1 source was stale but still usable.",
                )
            ]
        )
        current_report = _make_report(
            signals=[
                _make_signal(
                    code=STALE,
                    severity=WARNING,
                    message="3 sources were stale but still usable.",
                )
            ]
        )
        transition = _make_transition()

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        # Message text differs, but the code and severity match - this
        # must be treated as persistent with no severity change.
        assert explanation.persistent_signals == (STALE,)
        assert explanation.appeared_signals == ()
        assert explanation.resolved_signals == ()
        assert explanation.severity_changes == ()


class TestOrdering:
    """Test stable Commit #2 signal ordering is preserved."""

    def test_stable_signal_ordering_is_preserved(self):
        previous_report = _make_report(
            signals=[
                _make_signal(code=SKIPPED, severity=WARNING),
                _make_signal(code=DEGRADED, severity=WARNING),
            ]
        )
        current_report = _make_report(
            signals=[
                _make_signal(code=UNCOVERED, severity=WARNING),
                _make_signal(code=EXHAUSTED, severity=WARNING),
                _make_signal(code=DEGRADED, severity=CRITICAL_SEVERITY),
            ]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.appeared_signals == (EXHAUSTED, UNCOVERED)
        assert explanation.resolved_signals == (SKIPPED,)
        assert explanation.persistent_signals == (DEGRADED,)
        assert explanation.severity_changes[0].code == DEGRADED


class TestValidation:
    """Test rejection of mismatched or malformed inputs."""

    def test_different_projection_names_raise_error(self):
        previous_report = _make_report(projection_name="workspace.bootstrap")
        current_report = _make_report(projection_name="workspace.attention")
        transition = _make_transition(projection_name="workspace.bootstrap")

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError
        ):
            explainer.explain(
                previous_report=previous_report,
                current_report=current_report,
                transition=transition,
            )

    def test_previous_execution_id_mismatch_raises_error(self):
        previous_report = _make_report(execution_id="exec-a")
        current_report = _make_report(execution_id="exec-2")
        transition = _make_transition(
            previous_execution_id="exec-mismatch",
            current_execution_id="exec-2",
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError
        ):
            explainer.explain(
                previous_report=previous_report,
                current_report=current_report,
                transition=transition,
            )

    def test_current_execution_id_mismatch_raises_error(self):
        previous_report = _make_report(execution_id="exec-1")
        current_report = _make_report(execution_id="exec-b")
        transition = _make_transition(
            previous_execution_id="exec-1",
            current_execution_id="exec-mismatch",
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError
        ):
            explainer.explain(
                previous_report=previous_report,
                current_report=current_report,
                transition=transition,
            )

    def test_duplicate_signal_codes_are_rejected(self):
        previous_report = _make_report(
            signals=[
                _make_signal(code=STALE, severity=WARNING),
                _make_signal(code=STALE, severity=CRITICAL_SEVERITY),
            ]
        )
        current_report = _make_report(signals=[])
        transition = _make_transition()

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError
        ):
            explainer.explain(
                previous_report=previous_report,
                current_report=current_report,
                transition=transition,
            )


class TestEdgeCases:
    """Test empty reports and unchanged-health-with-signal-changes."""

    def test_empty_reports_produce_empty_explanation(self):
        previous_report = _make_report(signals=[])
        current_report = _make_report(signals=[])
        transition = _make_transition()

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.appeared_signals == ()
        assert explanation.resolved_signals == ()
        assert explanation.persistent_signals == ()
        assert explanation.severity_changes == ()

    def test_unchanged_health_can_still_have_signal_changes(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=SKIPPED, severity=WARNING)]
        )
        transition = _make_transition(
            previous_health=ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION,
            current_health=ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION,
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.transition == (
            ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED
        )
        assert explanation.appeared_signals == (SKIPPED,)
        assert explanation.resolved_signals == (STALE,)
        assert explanation.persistent_signals == ()


class TestDeterminism:
    """Test equivalent inputs produce equivalent explanations."""

    def test_equivalent_inputs_produce_equivalent_explanations(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=EXPIRED, severity=CRITICAL_SEVERITY)]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()

        explanation1 = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )
        explanation2 = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation1 == explanation2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the explainer."""

    def test_explainer_has_no_external_dependencies(self):
        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()

        assert explainer.__dict__ == {}

    def test_explainer_does_not_mutate_reports_or_transition(self):
        previous_report = _make_report(
            signals=[_make_signal(code=STALE, severity=WARNING)]
        )
        current_report = _make_report(
            signals=[_make_signal(code=EXPIRED, severity=CRITICAL_SEVERITY)]
        )
        transition = _make_transition(
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        )

        previous_dict = previous_report.to_dict()
        current_dict = current_report.to_dict()
        transition_dict = transition.to_dict()

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert previous_report.to_dict() == previous_dict
        assert current_report.to_dict() == current_dict
        assert transition.to_dict() == transition_dict

    def test_explainer_works_without_a_receipt(self):
        # No execution receipt is ever constructed here - proves the
        # explainer only needs the two reports and the transition.
        previous_report = _make_report(execution_id="report-only-previous")
        current_report = _make_report(
            execution_id="report-only-current",
            signals=[_make_signal(code=STALE, severity=WARNING)],
        )
        transition = _make_transition(
            previous_execution_id="report-only-previous",
            current_execution_id="report-only-current",
            kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.DETERIORATED,
        )

        explainer = ResearchWorkspaceConsumerProjectionHealthTransitionExplainer()
        explanation = explainer.explain(
            previous_report=previous_report,
            current_report=current_report,
            transition=transition,
        )

        assert explanation.appeared_signals == (STALE,)
