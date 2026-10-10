import pytest
from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
    ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter,
    ResearchWorkspaceConsumerProjectionExecutionStatus,
    ResearchWorkspaceConsumerProjectionFingerprint,
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
    ResearchWorkspaceConsumerProjectionIdentity,
    ResearchWorkspaceConsumerProjectionBudgetSummary,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
)


class TestExecutionReceiptFormatter:
    """Test execution receipt formatter."""

    def test_successful_receipt_formats_correctly(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="9c9af0123456789abcdef",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint=fingerprint,
        )

        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=7,
            degraded_stage_count=0,
            reused_resolution_count=3,
            total_duration_ms=42.5,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=4,
            fresh_source_count=3,
            stale_usable_source_count=1,
            expired_source_count=0,
            unknown_source_count=0,
        )

        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=1,
            exhausted=True,
        )

        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Execution: req-123" in output
        assert "Projection: workspace.bootstrap" in output
        assert "Contract: 1.0" in output
        assert "Status: succeeded" in output
        assert "Fingerprint: sha256:9c9af012..." in output
        assert "Diagnostics: 7 stages, 0 degraded, 3 reused, 42.5ms" in output
        assert "Freshness: 3 fresh, 1 stale-usable" in output
        assert "Budget: 3 admitted, 1 skipped, exhausted" in output
        assert "Provenance: 3/3 outputs covered" in output

    def test_degraded_receipt_formats_correctly(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint=fingerprint,
        )

        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=7,
            degraded_stage_count=1,
            reused_resolution_count=3,
            total_duration_ms=42.5,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=4,
            fresh_source_count=3,
            stale_usable_source_count=1,
            expired_source_count=0,
            unknown_source_count=0,
        )

        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=1,
            exhausted=False,
        )

        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Status: degraded" in output
        assert "1 degraded" in output

    def test_projection_name_is_included(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.attention",
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Projection: workspace.attention" in output

    def test_contract_version_is_included(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="2.5",
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Contract: 2.5" in output

    def test_execution_status_is_included(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Status: succeeded" in output

    def test_fingerprint_algorithm_and_value_are_included(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="9c9af0123456789abcdef",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            fingerprint=fingerprint,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Fingerprint: sha256:9c9af012..." in output

    def test_diagnostics_summary_is_represented_correctly(self):
        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=7,
            degraded_stage_count=1,
            reused_resolution_count=3,
            total_duration_ms=42.5,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Diagnostics: 7 stages, 1 degraded, 3 reused, 42.5ms" in output

    def test_freshness_summary_is_represented_correctly(self):
        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=4,
            fresh_source_count=3,
            stale_usable_source_count=1,
            expired_source_count=0,
            unknown_source_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=freshness,
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Freshness: 3 fresh, 1 stale-usable" in output

    def test_budget_summary_is_represented_correctly(self):
        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=1,
            exhausted=True,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=budget,
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Budget: 3 admitted, 1 skipped, exhausted" in output

    def test_provenance_coverage_is_represented_correctly(self):
        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Provenance: 3/3 outputs covered" in output

    def test_missing_contract_version_uses_fallback(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Contract: unspecified" in output

    def test_missing_fingerprint_uses_fallback(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Fingerprint: unavailable" in output

    def test_unbudgeted_execution_uses_fallback(self):
        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=False,
            admitted_stage_count=0,
            skipped_stage_count=0,
            exhausted=False,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=budget,
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Budget: unbudgeted" in output

    def test_missing_duration_omits_duration_from_diagnostics(self):
        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=7,
            degraded_stage_count=0,
            reused_resolution_count=3,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Diagnostics: 7 stages, 0 degraded, 3 reused" in output
        assert "ms" not in output

    def test_equivalent_receipts_produce_identical_output(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint=fingerprint,
        )

        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
            total_duration_ms=100.0,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=3,
            stale_usable_source_count=0,
            expired_source_count=0,
            unknown_source_count=0,
        )

        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=0,
            exhausted=False,
        )

        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        receipt1 = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        receipt2 = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output1 = formatter.format(receipt1)
        output2 = formatter.format(receipt2)

        assert output1 == output2

    def test_formatting_does_not_mutate_receipt(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint=fingerprint,
        )

        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
            total_duration_ms=100.0,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=3,
            stale_usable_source_count=0,
            expired_source_count=0,
            unknown_source_count=0,
        )

        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=0,
            exhausted=False,
        )

        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        original_dict = receipt.to_dict()

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        formatter.format(receipt)

        # Receipt should be unchanged
        assert receipt.to_dict() == original_dict

    def test_formatter_is_stateless(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint=fingerprint,
        )

        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
            total_duration_ms=100.0,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=3,
            stale_usable_source_count=0,
            expired_source_count=0,
            unknown_source_count=0,
        )

        budget = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=0,
            exhausted=False,
        )

        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()

        # Multiple calls should produce same result
        output1 = formatter.format(receipt)
        output2 = formatter.format(receipt)
        output3 = formatter.format(receipt)

        assert output1 == output2 == output3

    def test_freshness_with_expired_sources(self):
        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=1,
            stale_usable_source_count=0,
            expired_source_count=2,
            unknown_source_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=freshness,
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Freshness: 1 fresh, 2 expired" in output

    def test_freshness_with_unknown_sources(self):
        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=1,
            stale_usable_source_count=0,
            expired_source_count=0,
            unknown_source_count=2,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=freshness,
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Freshness: 1 fresh, 2 unknown" in output

    def test_provenance_with_uncovered_outputs(self):
        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=4,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=1,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Provenance: 3/4 outputs covered" in output

    def test_provenance_with_no_outputs(self):
        provenance = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=0,
            derivation_node_count=0,
            output_node_count=0,
            edge_count=0,
            covered_output_count=0,
            uncovered_output_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=ResearchWorkspaceConsumerProjectionFreshnessSummary(
                observed_source_count=0,
                fresh_source_count=0,
                stale_usable_source_count=0,
                expired_source_count=0,
                unknown_source_count=0,
            ),
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=provenance,
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Provenance: no outputs" in output

    def test_freshness_with_no_sources(self):
        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=0,
            fresh_source_count=0,
            stale_usable_source_count=0,
            expired_source_count=0,
            unknown_source_count=0,
        )

        receipt = ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id="req-123",
            observed_at=datetime.now(timezone.utc),
            identity=ResearchWorkspaceConsumerProjectionIdentity(
                projection_name="workspace.bootstrap",
            ),
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
                stage_count=1,
                degraded_stage_count=0,
                reused_resolution_count=0,
            ),
            freshness=freshness,
            budget=ResearchWorkspaceConsumerProjectionBudgetSummary(
                budgeted=False,
                admitted_stage_count=0,
                skipped_stage_count=0,
                exhausted=False,
            ),
            provenance=ResearchWorkspaceConsumerProjectionProvenanceSummary(
                source_node_count=0,
                derivation_node_count=0,
                output_node_count=0,
                edge_count=0,
                covered_output_count=0,
                uncovered_output_count=0,
            ),
        )

        formatter = ResearchWorkspaceConsumerProjectionExecutionReceiptFormatter()
        output = formatter.format(receipt)

        assert "Freshness: no sources observed" in output
