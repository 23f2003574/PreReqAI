import pytest
from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
    ResearchWorkspaceConsumerProjectionExecutionHealth,
    ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer,
    ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer,
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
    ResearchWorkspaceConsumerProjectionExecutionStatus,
    ResearchWorkspaceConsumerProjectionFingerprint,
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
    ResearchWorkspaceConsumerProjectionIdentity,
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
    ResearchWorkspaceConsumerProjectionQualitySignal,
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
    ResearchWorkspaceConsumerProjectionQualitySignalExtractor,
    ResearchWorkspaceConsumerProjectionQualitySignalReport,
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


def _make_signal(
    *,
    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED,
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


class _RecordingExtractor:
    def __init__(self, report_to_return):
        self.received_receipt = None
        self._report_to_return = report_to_return

    def extract(self, receipt):
        self.received_receipt = receipt
        return self._report_to_return


class _RecordingSummarizer:
    def __init__(self, summary_to_return):
        self.received_report = None
        self._summary_to_return = summary_to_return

    def summarize(self, report):
        self.received_report = report
        return self._summary_to_return


class TestHealthResolution:
    """Test health classification precedence rules."""

    def test_no_signals_produce_healthy(self):
        report = _make_report(signals=())

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
        )

    def test_info_only_signals_produce_healthy(self):
        report = _make_report(
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.INFO
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
        )

    def test_single_warning_produces_attention(self):
        report = _make_report(
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION
        )

    def test_multiple_warnings_produce_attention(self):
        report = _make_report(
            signals=[
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING,
                ),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION
        )

    def test_single_critical_produces_critical(self):
        report = _make_report(
            signals=[
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.CRITICAL
        )

    def test_critical_takes_precedence_over_warning(self):
        report = _make_report(
            signals=[
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXECUTION_DEGRADED,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING,
                ),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.UNKNOWN_FRESHNESS_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.INFO,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.CRITICAL
        )
        assert summary.signal_count == 3
        assert summary.warning_count == 1
        assert summary.critical_count == 1


class TestCounts:
    """Test signal/warning/critical counts are derived correctly."""

    def test_signal_count_is_correct(self):
        report = _make_report(
            signals=[
                _make_signal(),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.signal_count == 2

    def test_warning_count_is_correct(self):
        report = _make_report(
            signals=[
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.STALE_DATA_USED,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING,
                ),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.OPTIONAL_WORK_SKIPPED,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING,
                ),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.warning_count == 2

    def test_critical_count_is_correct(self):
        report = _make_report(
            signals=[
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.INCOMPLETE_PROVENANCE,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.critical_count == 2


class TestIdentityPreservation:
    """Test execution identity is reused, not regenerated."""

    def test_execution_id_is_preserved(self):
        report = _make_report(execution_id="req-123")

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.execution_id == "req-123"

    def test_projection_name_is_preserved(self):
        report = _make_report(projection_name="workspace.attention")

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.projection_name == "workspace.attention"


class TestDeterminism:
    """Test summarization is deterministic."""

    def test_equivalent_reports_produce_equivalent_summaries(self):
        report1 = _make_report(
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
                ),
            ]
        )
        report2 = _make_report(
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()

        assert summarizer.summarize(report1) == summarizer.summarize(report2)


class TestHasConcerns:
    """Test the has_concerns derived property."""

    def test_has_concerns_false_when_healthy(self):
        report = _make_report(signals=())

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.has_concerns is False

    def test_has_concerns_true_when_attention(self):
        report = _make_report(
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.has_concerns is True

    def test_has_concerns_true_when_critical(self):
        report = _make_report(
            signals=[
                _make_signal(
                    code=ResearchWorkspaceConsumerProjectionQualitySignalCode.EXPIRED_DATA_PRESENT,
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL,
                ),
            ]
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.has_concerns is True


class TestArchitecturalBoundaries:
    """Test structural guarantees of the summarizer."""

    def test_summarizer_has_no_external_dependencies(self):
        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()

        assert summarizer.__dict__ == {}

    def test_summarizer_does_not_mutate_report(self):
        report = _make_report(
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
                ),
            ]
        )
        original_dict = report.to_dict()

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summarizer.summarize(report)

        assert report.to_dict() == original_dict

    def test_summarizer_works_from_report_alone_without_a_receipt(self):
        # No ResearchWorkspaceConsumerProjectionExecutionReceipt is ever
        # constructed here - proves the summarizer only needs the report,
        # not receipt internals (diagnostics/freshness/budget/provenance).
        report = _make_report(
            execution_id="report-only-exec",
            projection_name="workspace.bootstrap",
            signals=[
                _make_signal(
                    severity=ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
                ),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        summary = summarizer.summarize(report)

        assert summary.execution_id == "report-only-exec"
        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION
        )


class TestExecutionHealthAnalyzer:
    """Test the optional composition analyzer."""

    def test_analyzer_delegates_to_extractor_and_summarizer(self):
        fake_report = _make_report(execution_id="delegated-exec")
        fake_summary = object()

        extractor = _RecordingExtractor(report_to_return=fake_report)
        summarizer = _RecordingSummarizer(summary_to_return=fake_summary)

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer(
            signal_extractor=extractor,
            health_summarizer=summarizer,
        )

        receipt = _make_receipt()
        result = analyzer.analyze(receipt)

        assert extractor.received_receipt is receipt
        assert summarizer.received_report is fake_report
        assert result is fake_summary

    def test_analyzer_does_not_duplicate_signal_extraction_logic(self):
        receipt = _make_receipt(
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED,
            stale_usable_source_count=1,
        )

        extractor = ResearchWorkspaceConsumerProjectionQualitySignalExtractor()
        summarizer = ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer()
        expected = summarizer.summarize(extractor.extract(receipt))

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer()
        actual = analyzer.analyze(receipt)

        assert actual == expected

    def test_analyzer_uses_default_extractor_and_summarizer_when_not_provided(self):
        receipt = _make_receipt()

        analyzer = ResearchWorkspaceConsumerProjectionExecutionHealthAnalyzer()
        summary = analyzer.analyze(receipt)

        assert (
            summary.health
            == ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
        )
