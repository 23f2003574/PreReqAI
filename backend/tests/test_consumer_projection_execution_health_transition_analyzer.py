import pytest
from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
    ResearchWorkspaceConsumerProjectionExecutionHealth,
    ResearchWorkspaceConsumerProjectionExecutionHealthSummary,
    ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer,
    ResearchWorkspaceConsumerProjectionExecutionHealthTransitionEvaluator,
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
    ResearchWorkspaceConsumerProjectionExecutionStatus,
    ResearchWorkspaceConsumerProjectionFingerprint,
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
    ResearchWorkspaceConsumerProjectionHealthTransitionError,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionIdentity,
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
)


def _make_summary(
    *,
    execution_id="exec-1",
    projection_name="workspace.bootstrap",
    health=ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY,
    signal_count=0,
    warning_count=0,
    critical_count=0,
):
    return ResearchWorkspaceConsumerProjectionExecutionHealthSummary(
        execution_id=execution_id,
        projection_name=projection_name,
        health=health,
        signal_count=signal_count,
        warning_count=warning_count,
        critical_count=critical_count,
    )


def _make_receipt(
    *,
    execution_id="exec-1",
    projection_name="workspace.bootstrap",
    contract_version="1.0",
    fingerprint_value="abc123",
    status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
    stage_count=5,
    degraded_stage_count=0,
    reused_resolution_count=0,
    total_duration_ms=None,
    fresh_source_count=4,
    stale_usable_source_count=0,
    expired_source_count=0,
    unknown_source_count=0,
    budgeted=True,
    admitted_stage_count=3,
    skipped_stage_count=0,
    exhausted=False,
    source_node_count=4,
    derivation_node_count=5,
    output_node_count=3,
    edge_count=9,
    covered_output_count=3,
    uncovered_output_count=0,
):
    fingerprint = None
    if fingerprint_value is not None:
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value=fingerprint_value,
        )

    identity = ResearchWorkspaceConsumerProjectionIdentity(
        projection_name=projection_name,
        contract_version=contract_version,
        fingerprint=fingerprint,
    )

    observed_source_count = (
        fresh_source_count
        + stale_usable_source_count
        + expired_source_count
        + unknown_source_count
    )

    return ResearchWorkspaceConsumerProjectionExecutionReceipt(
        execution_id=execution_id,
        observed_at=datetime.now(timezone.utc),
        identity=identity,
        status=status,
        diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=stage_count,
            degraded_stage_count=degraded_stage_count,
            reused_resolution_count=reused_resolution_count,
            total_duration_ms=total_duration_ms,
        ),
        freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=observed_source_count,
            fresh_source_count=fresh_source_count,
            stale_usable_source_count=stale_usable_source_count,
            expired_source_count=expired_source_count,
            unknown_source_count=unknown_source_count,
        ),
        budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=budgeted,
            admitted_stage_count=admitted_stage_count,
            skipped_stage_count=skipped_stage_count,
            exhausted=exhausted,
        ),
        provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=source_node_count,
            derivation_node_count=derivation_node_count,
            output_node_count=output_node_count,
            edge_count=edge_count,
            covered_output_count=covered_output_count,
            uncovered_output_count=uncovered_output_count,
        ),
    )


class _RecordingHealthAnalyzer:
    def __init__(self, summaries_by_execution_id):
        self._summaries_by_execution_id = summaries_by_execution_id
        self.received_receipts = []

    def analyze(self, receipt):
        self.received_receipts.append(receipt)
        return self._summaries_by_execution_id[receipt.execution_id]


class _RecordingTransitionAnalyzer:
    def __init__(self, transition_to_return):
        self._transition_to_return = transition_to_return
        self.received_args = None

    def analyze(self, previous, current):
        self.received_args = (previous, current)
        return self._transition_to_return


HEALTHY = ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
ATTENTION = ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION
CRITICAL = ResearchWorkspaceConsumerProjectionExecutionHealth.CRITICAL

UNCHANGED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED
IMPROVED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.IMPROVED
DETERIORATED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.DETERIORATED
RECOVERED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.RECOVERED
BECAME_CRITICAL = ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL


class TestTransitionResolution:
    """Test all nine (previous, current) health pairs."""

    @pytest.mark.parametrize(
        "previous_health,current_health,expected_kind",
        [
            (HEALTHY, HEALTHY, UNCHANGED),
            (ATTENTION, ATTENTION, UNCHANGED),
            (CRITICAL, CRITICAL, UNCHANGED),
            (ATTENTION, HEALTHY, RECOVERED),
            (CRITICAL, HEALTHY, RECOVERED),
            (CRITICAL, ATTENTION, IMPROVED),
            (HEALTHY, ATTENTION, DETERIORATED),
            (HEALTHY, CRITICAL, BECAME_CRITICAL),
            (ATTENTION, CRITICAL, BECAME_CRITICAL),
        ],
    )
    def test_transition_kind(
        self, previous_health, current_health, expected_kind
    ):
        previous = _make_summary(health=previous_health)
        current = _make_summary(health=current_health)

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.kind == expected_kind


class TestChangedProperty:
    """Test the derived `changed` property."""

    @pytest.mark.parametrize(
        "health",
        [HEALTHY, ATTENTION, CRITICAL],
    )
    def test_changed_is_false_for_stable_health(self, health):
        previous = _make_summary(health=health)
        current = _make_summary(health=health)

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.changed is False

    @pytest.mark.parametrize(
        "previous_health,current_health",
        [
            (ATTENTION, HEALTHY),
            (CRITICAL, HEALTHY),
            (CRITICAL, ATTENTION),
            (HEALTHY, ATTENTION),
            (HEALTHY, CRITICAL),
            (ATTENTION, CRITICAL),
        ],
    )
    def test_changed_is_true_for_moved_health(
        self, previous_health, current_health
    ):
        previous = _make_summary(health=previous_health)
        current = _make_summary(health=current_health)

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.changed is True


class TestIdentityPreservation:
    """Test execution identity is reused from the input summaries."""

    def test_previous_execution_id_is_preserved(self):
        previous = _make_summary(execution_id="req-previous")
        current = _make_summary(execution_id="req-current")

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.previous_execution_id == "req-previous"

    def test_current_execution_id_is_preserved(self):
        previous = _make_summary(execution_id="req-previous")
        current = _make_summary(execution_id="req-current")

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.current_execution_id == "req-current"

    def test_projection_name_is_preserved(self):
        previous = _make_summary(projection_name="workspace.attention")
        current = _make_summary(projection_name="workspace.attention")

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.projection_name == "workspace.attention"


class TestProjectionMismatch:
    """Test comparison is refused across different projections."""

    def test_different_projection_names_raise_error(self):
        previous = _make_summary(projection_name="workspace.bootstrap")
        current = _make_summary(projection_name="workspace.attention")

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionError
        ):
            analyzer.analyze(previous, current)


class TestDeterminism:
    """Test transition analysis is deterministic."""

    def test_equivalent_inputs_produce_equivalent_transitions(self):
        previous = _make_summary(health=CRITICAL)
        current = _make_summary(health=HEALTHY)

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()

        transition1 = analyzer.analyze(previous, current)
        transition2 = analyzer.analyze(previous, current)

        assert transition1 == transition2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the transition analyzer."""

    def test_analyzer_has_no_external_dependencies(self):
        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()

        assert analyzer.__dict__ == {}

    def test_analyzer_does_not_mutate_either_summary(self):
        previous = _make_summary(health=CRITICAL)
        current = _make_summary(health=HEALTHY)

        previous_dict = previous.to_dict()
        current_dict = current.to_dict()

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        analyzer.analyze(previous, current)

        assert previous.to_dict() == previous_dict
        assert current.to_dict() == current_dict

    def test_analyzer_works_from_summaries_alone_without_receipts(self):
        # No receipt or quality signal report is ever constructed here -
        # proves the analyzer only needs the two health summaries.
        previous = _make_summary(
            execution_id="summary-only-previous", health=ATTENTION
        )
        current = _make_summary(
            execution_id="summary-only-current", health=HEALTHY
        )

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionAnalyzer()
        transition = analyzer.analyze(previous, current)

        assert transition.kind == RECOVERED


class TestExecutionHealthTransitionEvaluator:
    """Test the optional receipt-to-receipt composition evaluator."""

    def test_evaluator_delegates_to_health_analyzer_and_transition_analyzer(self):
        previous_receipt = _make_receipt(execution_id="exec-previous")
        current_receipt = _make_receipt(execution_id="exec-current")

        previous_summary = _make_summary(execution_id="exec-previous")
        current_summary = _make_summary(execution_id="exec-current")

        health_analyzer = _RecordingHealthAnalyzer(
            {
                "exec-previous": previous_summary,
                "exec-current": current_summary,
            }
        )
        fake_transition = object()
        transition_analyzer = _RecordingTransitionAnalyzer(
            transition_to_return=fake_transition
        )

        evaluator = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionEvaluator(
            health_analyzer=health_analyzer,
            transition_analyzer=transition_analyzer,
        )

        result = evaluator.evaluate(previous_receipt, current_receipt)

        assert health_analyzer.received_receipts == [
            previous_receipt,
            current_receipt,
        ]
        assert transition_analyzer.received_args == (
            previous_summary,
            current_summary,
        )
        assert result is fake_transition

    def test_evaluator_does_not_duplicate_analysis_logic(self):
        previous_receipt = _make_receipt(
            execution_id="exec-previous",
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            expired_source_count=1,
        )
        current_receipt = _make_receipt(execution_id="exec-current")

        evaluator = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionEvaluator()
        actual = evaluator.evaluate(previous_receipt, current_receipt)

        health_analyzer = evaluator._health_analyzer
        transition_analyzer = evaluator._transition_analyzer
        expected = transition_analyzer.analyze(
            health_analyzer.analyze(previous_receipt),
            health_analyzer.analyze(current_receipt),
        )

        assert actual == expected

    def test_evaluator_uses_default_components_when_not_provided(self):
        previous_receipt = _make_receipt(
            execution_id="exec-previous",
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            expired_source_count=1,
        )
        current_receipt = _make_receipt(execution_id="exec-current")

        evaluator = ResearchWorkspaceConsumerProjectionExecutionHealthTransitionEvaluator()
        transition = evaluator.evaluate(previous_receipt, current_receipt)

        assert transition.previous_health == CRITICAL
        assert transition.current_health == HEALTHY
        assert transition.kind == RECOVERED
