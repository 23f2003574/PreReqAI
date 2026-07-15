import pytest
from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
    ResearchWorkspaceConsumerProjectionExecutionStatus,
    ResearchWorkspaceConsumerProjectionFingerprint,
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
    ResearchWorkspaceConsumerProjectionIdentity,
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
    ResearchWorkspaceConsumerProjectionQualitySignalExtractor,
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
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


def _codes(report):
    return [signal.code for signal in report.signals]


class TestHealthyReceipt:
    """Test that a fully healthy receipt produces no signals."""

    def test_healthy_receipt_produces_no_signals(self):
        receipt = _make_receipt()

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert report.signals == ()
        assert report.signal_count == 0
        assert report.has_warnings is False
        assert report.has_critical_signals is False


class TestIndividualSignals:
    """Test each signal is extracted from its corresponding receipt fact."""

    def test_degraded_status_produces_execution_degraded(self):
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert (
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED
            in _codes(report)
        )

    def test_succeeded_status_does_not_produce_execution_degraded(self):
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert (
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED
            not in _codes(report)
        )

    def test_stale_usable_sources_produce_stale_data_used(self):
        receipt = _make_receipt(stale_usable_source_count=1)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        signal = report.signals[0]
        assert (
            signal.code
            == ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED
        )
        assert signal.value == 1

    def test_expired_sources_produce_expired_data_present(self):
        receipt = _make_receipt(expired_source_count=2)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        signal = report.signals[0]
        assert (
            signal.code
            == ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT
        )
        assert signal.value == 2

    def test_unknown_freshness_produces_unknown_freshness_present(self):
        receipt = _make_receipt(unknown_source_count=1)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        signal = report.signals[0]
        assert (
            signal.code
            == ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT
        )
        assert signal.value == 1

    def test_budget_exhaustion_produces_budget_exhausted(self):
        receipt = _make_receipt(budgeted=True, exhausted=True)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert (
            ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED
            in _codes(report)
        )

    def test_unbudgeted_execution_does_not_produce_budget_exhausted(self):
        # budgeted=False, exhausted=True would be an inconsistent receipt in
        # practice, but the extractor must still respect "unbudgeted means
        # no budget signal" rather than trusting the exhausted flag alone.
        receipt = _make_receipt(budgeted=False, exhausted=True)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert (
            ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED
            not in _codes(report)
        )

    def test_skipped_optional_work_produces_optional_work_skipped(self):
        receipt = _make_receipt(skipped_stage_count=2)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        signal = report.signals[0]
        assert (
            signal.code
            == ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED
        )
        assert signal.value == 2

    def test_uncovered_outputs_produce_incomplete_provenance(self):
        receipt = _make_receipt(
            covered_output_count=3, uncovered_output_count=1
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        signal = report.signals[0]
        assert (
            signal.code
            == ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE
        )
        assert signal.value == 1


class TestMultipleConditions:
    """Test combinations of conditions and stable ordering."""

    def test_multiple_conditions_produce_multiple_signals(self):
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            expired_source_count=1,
            unknown_source_count=1,
            budgeted=True,
            exhausted=True,
            skipped_stage_count=2,
            covered_output_count=0,
            uncovered_output_count=1,
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert _codes(report) == [
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE,
        ]

    def test_signal_ordering_is_deterministic(self):
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            stale_usable_source_count=1,
            expired_source_count=1,
            unknown_source_count=1,
            budgeted=True,
            exhausted=True,
            skipped_stage_count=1,
            uncovered_output_count=1,
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()

        report1 = extractor.extract(receipt)
        report2 = extractor.extract(receipt)

        assert _codes(report1) == _codes(report2) == [
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.BUDGET_EXHAUSTED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED,
            ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE,
        ]

    def test_equivalent_receipts_produce_equivalent_reports(self):
        receipt1 = _make_receipt(
            execution_id="exec-a",
            stale_usable_source_count=1,
        )
        receipt2 = _make_receipt(
            execution_id="exec-a",
            stale_usable_source_count=1,
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()

        report1 = extractor.extract(receipt1)
        report2 = extractor.extract(receipt2)

        assert report1 == report2


class TestSeverityFlags:
    """Test has_warnings / has_critical_signals derivation."""

    def test_has_warnings_true_when_warning_signal_present(self):
        receipt = _make_receipt(skipped_stage_count=1)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert report.has_warnings is True
        assert report.has_critical_signals is False

    def test_has_critical_signals_true_when_critical_signal_present(self):
        receipt = _make_receipt(expired_source_count=1)

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert report.has_critical_signals is True
        assert (
            report.signals[0].severity
            == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL
        )

    def test_empty_signal_report_exposes_both_flags_as_false(self):
        receipt = _make_receipt()

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert report.signals == ()
        assert report.has_warnings is False
        assert report.has_critical_signals is False


class TestArchitecturalBoundaries:
    """Test structural guarantees of the extractor."""

    def test_extractor_has_no_external_dependencies(self):
        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()

        assert extractor.__dict__ == {}

    def test_extractor_does_not_mutate_receipt(self):
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            stale_usable_source_count=1,
        )
        original_dict = receipt.to_dict()

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        extractor.extract(receipt)

        assert receipt.to_dict() == original_dict

    def test_extractor_trusts_receipt_status_without_recomputation(self):
        # Diagnostics/freshness/budget/provenance are all "healthy" here,
        # yet the receipt's own status field says DEGRADED. A resolver
        # that recomputed status from the summaries would disagree with
        # the receipt; the extractor must trust the stored status instead.
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            degraded_stage_count=0,
            stale_usable_source_count=0,
            expired_source_count=0,
            skipped_stage_count=0,
            exhausted=False,
            uncovered_output_count=0,
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        report = extractor.extract(receipt)

        assert _codes(report) == [
            ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED
        ]
