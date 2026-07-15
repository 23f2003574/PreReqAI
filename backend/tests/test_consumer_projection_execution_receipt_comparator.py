import pytest
from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
    ResearchWorkspaceConsumerProjectionExecutionReceiptComparator,
    ResearchWorkspaceConsumerProjectionExecutionStatus,
    ResearchWorkspaceConsumerProjectionFingerprint,
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
    ResearchWorkspaceConsumerProjectionIdentity,
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
    ResearchWorkspaceConsumerProjectionReceiptChangeKind,
    ResearchWorkspaceConsumerProjectionReceiptComparisonError,
)


def _make_receipt(
    *,
    execution_id="exec-1",
    projection_name="workspace.bootstrap",
    contract_version="1.0",
    fingerprint_value="abc123",
    fingerprint_algorithm=(
        ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256
    ),
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
            algorithm=fingerprint_algorithm,
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


def _changes_by_field(comparison):
    return {change.field: change for change in comparison.changes}


class TestBasicComparison:
    """Test baseline comparison behavior."""

    def test_equivalent_receipts_produce_unchanged(self):
        previous = _make_receipt()
        current = _make_receipt()

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.UNCHANGED
        )
        assert comparison.semantic_state_changed is False
        assert comparison.execution_conditions_changed is False
        assert comparison.changes == ()

    def test_different_execution_ids_alone_do_not_count_as_change(self):
        previous = _make_receipt(execution_id="exec-previous")
        current = _make_receipt(execution_id="exec-current")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert comparison.changes == ()
        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.UNCHANGED
        )
        assert comparison.previous_execution_id == "exec-previous"
        assert comparison.current_execution_id == "exec-current"

    def test_different_projection_names_cannot_be_compared(self):
        previous = _make_receipt(projection_name="workspace.bootstrap")
        current = _make_receipt(projection_name="workspace.attention")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReceiptComparisonError
        ):
            comparator.compare(previous, current)

    def test_comparison_is_deterministic(self):
        previous = _make_receipt(status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED)
        current = _make_receipt()

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()

        comparison1 = comparator.compare(previous, current)
        comparison2 = comparator.compare(previous, current)

        assert comparison1 == comparison2


class TestSemanticIdentity:
    """Test fingerprint-based semantic state comparison."""

    def test_same_fingerprint_sets_semantic_state_changed_false(self):
        previous = _make_receipt(fingerprint_value="abc123")
        current = _make_receipt(fingerprint_value="abc123")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert comparison.semantic_state_changed is False

    def test_different_fingerprint_sets_semantic_state_changed_true(self):
        previous = _make_receipt(fingerprint_value="abc123")
        current = _make_receipt(fingerprint_value="def456")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert comparison.semantic_state_changed is True

    def test_fingerprint_change_is_classified_as_changed(self):
        previous = _make_receipt(fingerprint_value="abc123")
        current = _make_receipt(fingerprint_value="def456")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["fingerprint"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )

    def test_fingerprint_only_change_leaves_execution_conditions_unchanged(self):
        previous = _make_receipt(fingerprint_value="abc123")
        current = _make_receipt(fingerprint_value="def456")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert comparison.execution_conditions_changed is False
        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )

    def test_comparator_relies_only_on_stored_fingerprint_equality(self):
        # Two distinct fingerprint instances with identical algorithm and
        # value must be treated as unchanged - the comparator must never
        # recompute or otherwise second-guess the stored fingerprint.
        previous = _make_receipt(fingerprint_value="abc123")
        current = _make_receipt(fingerprint_value="abc123")

        assert previous.identity.fingerprint is not current.identity.fingerprint

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert comparison.semantic_state_changed is False
        assert "fingerprint" not in _changes_by_field(comparison)


class TestStatus:
    """Test execution status comparison."""

    def test_succeeded_to_degraded_is_degradation(self):
        previous = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        )
        current = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["status"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_degraded_to_succeeded_is_improvement(self):
        previous = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
        )
        current = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["status"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )

    def test_same_status_produces_no_status_change(self):
        previous = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        )
        current = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert "status" not in _changes_by_field(comparison)


class TestContract:
    """Test contract version comparison."""

    def test_contract_version_difference_is_recorded(self):
        previous = _make_receipt(contract_version="1.0")
        current = _make_receipt(contract_version="1.1")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert "contract_version" in changes
        assert changes["contract_version"].previous == "1.0"
        assert changes["contract_version"].current == "1.1"

    def test_contract_version_change_is_classified_as_changed(self):
        previous = _make_receipt(contract_version="1.0")
        current = _make_receipt(contract_version="1.1")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["contract_version"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )

    def test_contract_version_change_does_not_count_as_execution_condition_change(self):
        previous = _make_receipt(contract_version="1.0")
        current = _make_receipt(contract_version="1.1")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert comparison.execution_conditions_changed is False
        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )


class TestFreshness:
    """Test freshness summary comparison."""

    def test_increased_expired_sources_is_degradation(self):
        previous = _make_receipt(fresh_source_count=4, expired_source_count=0)
        current = _make_receipt(fresh_source_count=3, expired_source_count=1)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["freshness"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_increased_stale_sources_is_degradation(self):
        previous = _make_receipt(fresh_source_count=4, stale_usable_source_count=0)
        current = _make_receipt(fresh_source_count=3, stale_usable_source_count=1)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["freshness"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_reduced_stale_and_expired_sources_is_improvement(self):
        previous = _make_receipt(
            fresh_source_count=1,
            stale_usable_source_count=1,
            expired_source_count=1,
        )
        current = _make_receipt(
            fresh_source_count=3,
            stale_usable_source_count=0,
            expired_source_count=0,
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["freshness"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )

    def test_equivalent_freshness_summaries_produce_no_change(self):
        previous = _make_receipt(fresh_source_count=4)
        current = _make_receipt(fresh_source_count=4)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert "freshness" not in _changes_by_field(comparison)

    def test_offsetting_freshness_changes_produce_changed(self):
        previous = _make_receipt(
            stale_usable_source_count=1,
            unknown_source_count=0,
        )
        current = _make_receipt(
            stale_usable_source_count=0,
            unknown_source_count=1,
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["freshness"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )


class TestBudget:
    """Test budget summary comparison."""

    def test_more_pressure_induced_skips_is_degradation(self):
        previous = _make_receipt(skipped_stage_count=0)
        current = _make_receipt(skipped_stage_count=2)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["budget"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_fewer_skips_is_improvement(self):
        previous = _make_receipt(skipped_stage_count=2)
        current = _make_receipt(skipped_stage_count=0)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["budget"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )

    def test_exhaustion_transition_to_true_is_degradation(self):
        previous = _make_receipt(exhausted=False)
        current = _make_receipt(exhausted=True)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["budget"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_exhaustion_transition_to_false_is_improvement(self):
        previous = _make_receipt(exhausted=True)
        current = _make_receipt(exhausted=False)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["budget"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )


class TestDiagnostics:
    """Test diagnostics summary comparison."""

    def test_increased_degraded_stage_count_is_degradation(self):
        previous = _make_receipt(degraded_stage_count=0)
        current = _make_receipt(degraded_stage_count=1)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["diagnostics"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_reduced_degraded_stage_count_is_improvement(self):
        previous = _make_receipt(degraded_stage_count=2)
        current = _make_receipt(degraded_stage_count=0)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["diagnostics"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )

    def test_duration_only_difference_does_not_invent_performance_thresholds(self):
        previous = _make_receipt(total_duration_ms=40.0)
        current = _make_receipt(total_duration_ms=4000.0)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["diagnostics"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )


class TestProvenance:
    """Test provenance summary comparison."""

    def test_increased_uncovered_output_count_is_degradation(self):
        previous = _make_receipt(covered_output_count=3, uncovered_output_count=0)
        current = _make_receipt(covered_output_count=3, uncovered_output_count=1)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["provenance"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_reduced_uncovered_output_count_is_improvement(self):
        previous = _make_receipt(covered_output_count=2, uncovered_output_count=2)
        current = _make_receipt(covered_output_count=4, uncovered_output_count=0)

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        changes = _changes_by_field(comparison)
        assert (
            changes["provenance"].kind
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )


class TestOverallResolution:
    """Test overall change precedence rules."""

    def test_no_changes_produce_unchanged(self):
        previous = _make_receipt()
        current = _make_receipt()

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.UNCHANGED
        )

    def test_any_degradation_takes_precedence_over_improvement(self):
        # Freshness improves while budget degrades - overall must be
        # DEGRADED so a regression is never hidden by an improvement.
        previous = _make_receipt(
            stale_usable_source_count=1,
            skipped_stage_count=0,
        )
        current = _make_receipt(
            stale_usable_source_count=0,
            skipped_stage_count=2,
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.DEGRADED
        )

    def test_improvements_without_degradation_produce_improved(self):
        previous = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            skipped_stage_count=1,
        )
        current = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            skipped_stage_count=0,
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.IMPROVED
        )

    def test_non_directional_differences_produce_changed(self):
        previous = _make_receipt(fingerprint_value="abc123")
        current = _make_receipt(fingerprint_value="def456")

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        assert (
            comparison.overall_change
            == ResearchWorkspaceConsumerProjectionReceiptChangeKind.CHANGED
        )


class TestArchitecturalBoundaries:
    """Test structural guarantees of the comparator."""

    def test_comparator_has_no_external_dependencies(self):
        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()

        # No repositories, clock, or projection services are held -
        # the comparator is a pure, stateless function object.
        assert comparator.__dict__ == {}

    def test_comparator_does_not_mutate_either_receipt(self):
        previous = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
        )
        current = _make_receipt()

        previous_dict = previous.to_dict()
        current_dict = current.to_dict()

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparator.compare(previous, current)

        assert previous.to_dict() == previous_dict
        assert current.to_dict() == current_dict

    def test_change_ordering_is_stable(self):
        previous = _make_receipt(
            contract_version="1.0",
            fingerprint_value="abc123",
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            degraded_stage_count=0,
            stale_usable_source_count=0,
            skipped_stage_count=0,
            uncovered_output_count=0,
        )
        current = _make_receipt(
            contract_version="1.1",
            fingerprint_value="def456",
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            degraded_stage_count=1,
            stale_usable_source_count=1,
            skipped_stage_count=1,
            uncovered_output_count=1,
        )

        comparator = ResearchWorkspaceConsumerProjectionExecutionReceiptComparator()
        comparison = comparator.compare(previous, current)

        observed_order = [change.field for change in comparison.changes]
        assert observed_order == [
            "contract_version",
            "fingerprint",
            "status",
            "diagnostics",
            "freshness",
            "budget",
            "provenance",
        ]
