import pytest
from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchWorkspaceConsumerProjectionBudgetAdmission,
    ResearchWorkspaceConsumerProjectionBudgetDecision,
    ResearchWorkspaceConsumerProjectionBudgetDecisionReason,
    ResearchWorkspaceConsumerProjectionBudgetSnapshot,
    ResearchWorkspaceConsumerProjectionBudgetSummary,
    ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer,
    ResearchWorkspaceConsumerProjectionDiagnosticsCollector,
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
    ResearchWorkspaceConsumerProjectionDiagnosticsStatus,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
    ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver,
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
    ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder,
    ResearchWorkspaceConsumerProjectionExecutionReceiptVerifier,
    ResearchWorkspaceConsumerProjectionExecutionStatus,
    ResearchWorkspaceConsumerProjectionFingerprint,
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
    ResearchWorkspaceConsumerProjectionFreshnessEvaluation,
    ResearchWorkspaceConsumerProjectionFreshnessReason,
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
    ResearchWorkspaceConsumerProjectionFreshnessSummarizer,
    ResearchWorkspaceConsumerProjectionIdentity,
    ResearchWorkspaceConsumerProjectionInputDiagnostic,
    ResearchWorkspaceConsumerProjectionOutputProvenance,
    ResearchWorkspaceConsumerProjectionProvenanceCollector,
    ResearchWorkspaceConsumerProjectionProvenanceReport,
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
    ResearchWorkspaceConsumerProjectionProvenanceSummarizer,
    ResearchWorkspaceConsumerProjectionReceiptVerificationIssue,
    ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode,
    ResearchWorkspaceConsumerProjectionReceiptVerificationReport,
    ResearchWorkspaceConsumerProjectionReceiptVerificationStatus,
    ResearchWorkspaceConsumerProjectionStageDiagnostic,
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


class TestExecutionStatus:
    """Test execution status enum."""

    def test_succeeded_value(self):
        assert (
            ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED.value
            == "succeeded"
        )

    def test_degraded_value(self):
        assert (
            ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED.value
            == "degraded"
        )


class TestProjectionIdentity:
    """Test projection identity model."""

    def test_identity_creation(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint=fingerprint,
        )

        assert identity.projection_name == "workspace.bootstrap"
        assert identity.contract_version == "1.0"
        assert identity.fingerprint == fingerprint

    def test_identity_without_contract_version(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
        )

        assert identity.contract_version is None

    def test_identity_without_fingerprint(self):
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
        )

        assert identity.fingerprint is None

    def test_identity_is_immutable(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            fingerprint=fingerprint,
        )

        with pytest.raises(Exception):  # Frozen dataclass
            identity.projection_name = "other"


class TestDiagnosticsSummary:
    """Test diagnostics summary model."""

    def test_summary_creation(self):
        summary = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=1,
            reused_resolution_count=3,
            total_duration_ms=42.5,
        )

        assert summary.stage_count == 5
        assert summary.degraded_stage_count == 1
        assert summary.reused_resolution_count == 3
        assert summary.total_duration_ms == 42.5

    def test_summary_without_duration(self):
        summary = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
        )

        assert summary.total_duration_ms is None

    def test_summary_is_immutable(self):
        summary = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
        )

        with pytest.raises(Exception):  # Frozen dataclass
            summary.stage_count = 10


class TestFreshnessSummary:
    """Test freshness summary model."""

    def test_summary_creation(self):
        summary = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=4,
            fresh_source_count=3,
            stale_usable_source_count=1,
            expired_source_count=0,
            unknown_source_count=0,
        )

        assert summary.observed_source_count == 4
        assert summary.fresh_source_count == 3
        assert summary.stale_usable_source_count == 1
        assert summary.expired_source_count == 0
        assert summary.unknown_source_count == 0

    def test_summary_is_immutable(self):
        summary = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=4,
            fresh_source_count=4,
            stale_usable_source_count=0,
            expired_source_count=0,
            unknown_source_count=0,
        )

        with pytest.raises(Exception):  # Frozen dataclass
            summary.fresh_source_count = 5


class TestBudgetSummary:
    """Test budget summary model."""

    def test_summary_creation(self):
        summary = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=1,
            exhausted=True,
        )

        assert summary.budgeted is True
        assert summary.admitted_stage_count == 3
        assert summary.skipped_stage_count == 1
        assert summary.exhausted is True

    def test_summary_unbudgeted(self):
        summary = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=False,
            admitted_stage_count=0,
            skipped_stage_count=0,
            exhausted=False,
        )

        assert summary.budgeted is False

    def test_summary_is_immutable(self):
        summary = ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=True,
            admitted_stage_count=3,
            skipped_stage_count=0,
            exhausted=False,
        )

        with pytest.raises(Exception):  # Frozen dataclass
            summary.admitted_stage_count = 5


class TestProvenanceSummary:
    """Test provenance summary model."""

    def test_summary_creation(self):
        summary = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        assert summary.source_node_count == 4
        assert summary.derivation_node_count == 5
        assert summary.output_node_count == 3
        assert summary.edge_count == 9
        assert summary.covered_output_count == 3
        assert summary.uncovered_output_count == 0

    def test_summary_with_uncovered_outputs(self):
        summary = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=4,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=1,
        )

        assert summary.uncovered_output_count == 1

    def test_summary_is_immutable(self):
        summary = ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=4,
            derivation_node_count=5,
            output_node_count=3,
            edge_count=9,
            covered_output_count=3,
            uncovered_output_count=0,
        )

        with pytest.raises(Exception):  # Frozen dataclass
            summary.covered_output_count = 4


class TestDiagnosticsSummarizer:
    """Test diagnostics summarizer."""

    def test_summarize_stage_count(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            stages=[
                ResearchWorkspaceConsumerProjectionStageDiagnostic(
                    name="stage1",
                    kind=ResearchWorkspaceConsumerProjectionDiagnosticsStageHelper.get_stage_kind("resolution"),
                    status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
                    duration_ms=10.0,
                    reason_code=None,
                    failure=None,
                )
                for _ in range(5)
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer()
        summary = summarizer.summarize(report)

        assert summary.stage_count == 5

    def test_summarize_degraded_stage_count(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            stages=[
                ResearchWorkspaceConsumerProjectionStageDiagnostic(
                    name=f"stage{i}",
                    kind=ResearchWorkspaceConsumerProjectionDiagnosticsStageHelper.get_stage_kind("resolution"),
                    status=(
                        ResearchWorkspaceConsumerProjectionDiagnosticsStatus.DEGRADED
                        if i == 0
                        else ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED
                    ),
                    duration_ms=10.0,
                    reason_code=None,
                    failure=None,
                )
                for i in range(5)
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer()
        summary = summarizer.summarize(report)

        assert summary.degraded_stage_count == 1

    def test_summarize_reused_resolution_count(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            inputs=[
                ResearchWorkspaceConsumerProjectionInputDiagnostic(
                    name="input1",
                    key=None,
                    resolution_count=1,
                    reuse_count=3,
                    duration_ms=10.0,
                    status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
                    failure=None,
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer()
        summary = summarizer.summarize(report)

        assert summary.reused_resolution_count == 3

    def test_summarize_total_duration(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=42.5,
        )

        summarizer = ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer()
        summary = summarizer.summarize(report)

        assert summary.total_duration_ms == 42.5


class TestFreshnessSummarizer:
    """Test freshness summarizer."""

    def test_summarize_fresh_sources(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            inputs=[
                ResearchWorkspaceConsumerProjectionInputDiagnostic(
                    name=f"input{i}",
                    key=None,
                    resolution_count=1,
                    reuse_count=0,
                    duration_ms=10.0,
                    status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
                    failure=None,
                    freshness=ResearchWorkspaceConsumerProjectionFreshnessEvaluation(
                        source_name=f"input{i}",
                        status=ResearchWorkspaceConsumerProjectionFreshnessStatus.FRESH,
                        reason=ResearchWorkspaceConsumerProjectionFreshnessReason.WITHIN_THRESHOLD,
                        source_timestamp=datetime.now(timezone.utc),
                        evaluated_at=datetime.now(timezone.utc),
                        age_ms=1000.0,
                        fresh_for_ms=5000.0,
                        usable_for_ms=10000.0,
                    ),
                )
                for i in range(3)
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionFreshnessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.fresh_source_count == 3

    def test_summarize_stale_usable_sources(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            inputs=[
                ResearchWorkspaceConsumerProjectionInputDiagnostic(
                    name="input1",
                    key=None,
                    resolution_count=1,
                    reuse_count=0,
                    duration_ms=10.0,
                    status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
                    failure=None,
                    freshness=ResearchWorkspaceConsumerProjectionFreshnessEvaluation(
                        source_name="input1",
                        status=ResearchWorkspaceConsumerProjectionFreshnessStatus.STALE,
                        reason=ResearchWorkspaceConsumerProjectionFreshnessReason.EXCEEDED_THRESHOLD,
                        source_timestamp=datetime.now(timezone.utc),
                        evaluated_at=datetime.now(timezone.utc),
                        age_ms=6000.0,
                        fresh_for_ms=5000.0,
                        usable_for_ms=10000.0,
                    ),
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionFreshnessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.stale_usable_source_count == 1

    def test_summarize_expired_sources(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            inputs=[
                ResearchWorkspaceConsumerProjectionInputDiagnostic(
                    name="input1",
                    key=None,
                    resolution_count=1,
                    reuse_count=0,
                    duration_ms=10.0,
                    status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
                    failure=None,
                    freshness=ResearchWorkspaceConsumerProjectionFreshnessEvaluation(
                        source_name="input1",
                        status=ResearchWorkspaceConsumerProjectionFreshnessStatus.UNUSABLE,
                        reason=ResearchWorkspaceConsumerProjectionFreshnessReason.EXCEEDED_USABLE_THRESHOLD,
                        source_timestamp=datetime.now(timezone.utc),
                        evaluated_at=datetime.now(timezone.utc),
                        age_ms=15000.0,
                        fresh_for_ms=5000.0,
                        usable_for_ms=10000.0,
                    ),
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionFreshnessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.expired_source_count == 1

    def test_summarize_unknown_sources(self):
        report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            inputs=[
                ResearchWorkspaceConsumerProjectionInputDiagnostic(
                    name="input1",
                    key=None,
                    resolution_count=1,
                    reuse_count=0,
                    duration_ms=10.0,
                    status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
                    failure=None,
                    freshness=None,
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionFreshnessSummarizer()
        summary = summarizer.summarize(report)

        assert summary.unknown_source_count == 1


class TestBudgetSummarizer:
    """Test budget summarizer."""

    def test_summarize_budgeted_execution(self):
        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            budget_decisions=[
                ResearchWorkspaceConsumerProjectionBudgetAdmission(
                    stage_name="stage1",
                    decision=ResearchWorkspaceConsumerProjectionBudgetDecision.EXECUTE,
                    reason=ResearchWorkspaceConsumerProjectionBudgetDecisionReason.WITHIN_BUDGET,
                    requirement=ResearchWorkspaceConsumerProjectionStageRequirement.OPTIONAL,
                    elapsed_ms=100.0,
                    remaining_ms=900.0,
                    minimum_remaining_budget_ms=0.0,
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer()
        summary = summarizer.summarize(
            budget_snapshot=budget_snapshot,
            diagnostic_report=diagnostic_report,
        )

        assert summary.budgeted is True
        assert summary.admitted_stage_count == 1

    def test_summarize_skipped_stages(self):
        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=900.0,
            remaining_ms=100.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
            budget_decisions=[
                ResearchWorkspaceConsumerProjectionBudgetAdmission(
                    stage_name="stage1",
                    decision=ResearchWorkspaceConsumerProjectionBudgetDecision.SKIP,
                    reason=ResearchWorkspaceConsumerProjectionBudgetDecisionReason.INSUFFICIENT_REMAINING_BUDGET,
                    requirement=ResearchWorkspaceConsumerProjectionStageRequirement.OPTIONAL,
                    elapsed_ms=900.0,
                    remaining_ms=100.0,
                    minimum_remaining_budget_ms=200.0,
                )
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer()
        summary = summarizer.summarize(
            budget_snapshot=budget_snapshot,
            diagnostic_report=diagnostic_report,
        )

        assert summary.skipped_stage_count == 1

    def test_summarize_exhausted_budget(self):
        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=1100.0,
            remaining_ms=0.0,
            overrun_ms=100.0,
            exhausted=True,
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        summarizer = ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer()
        summary = summarizer.summarize(
            budget_snapshot=budget_snapshot,
            diagnostic_report=diagnostic_report,
        )

        assert summary.exhausted is True

    def test_summarize_unbudgeted_execution(self):
        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=None,
            elapsed_ms=500.0,
            remaining_ms=None,
            overrun_ms=0.0,
            exhausted=False,
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="test",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        summarizer = ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer()
        summary = summarizer.summarize(
            budget_snapshot=budget_snapshot,
            diagnostic_report=diagnostic_report,
        )

        assert summary.budgeted is False


class TestProvenanceSummarizer:
    """Test provenance summarizer."""

    def test_summarize_node_counts(self):
        report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="test",
            sources=[
                type("obj", (object,), {"node_id": f"source{i}"})()
                for i in range(4)
            ],
            derivations=[
                type("obj", (object,), {"node_id": f"derivation{i}"})()
                for i in range(5)
            ],
            outputs=[
                type("obj", (object,), {"node_id": f"output{i}"})()
                for i in range(3)
            ],
            edges=[
                type("obj", (object,), {"to_node_id": "output0", "from_node_id": "source0"})()
                for _ in range(9)
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionProvenanceSummarizer()
        summary = summarizer.summarize(report)

        assert summary.source_node_count == 4
        assert summary.derivation_node_count == 5
        assert summary.output_node_count == 3
        assert summary.edge_count == 9

    def test_summarize_covered_outputs(self):
        report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="test",
            sources=[
                type("obj", (object,), {"node_id": "source0"})()
            ],
            derivations=[],
            outputs=[
                type("obj", (object,), {"node_id": f"output{i}"})()
                for i in range(3)
            ],
            edges=[
                type("obj", (object,), {"to_node_id": "output0", "from_node_id": "source0"})(),
                type("obj", (object,), {"to_node_id": "output1", "from_node_id": "source0"})(),
                type("obj", (object,), {"to_node_id": "output2", "from_node_id": "source0"})(),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionProvenanceSummarizer()
        summary = summarizer.summarize(report)

        assert summary.covered_output_count == 3
        assert summary.uncovered_output_count == 0

    def test_summarize_uncovered_outputs(self):
        report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="test",
            sources=[
                type("obj", (object,), {"node_id": "source0"})()
            ],
            derivations=[],
            outputs=[
                type("obj", (object,), {"node_id": f"output{i}"})()
                for i in range(4)
            ],
            edges=[
                type("obj", (object,), {"to_node_id": "output0", "from_node_id": "source0"})(),
                type("obj", (object,), {"to_node_id": "output1", "from_node_id": "source0"})(),
                type("obj", (object,), {"to_node_id": "output2", "from_node_id": "source0"})(),
            ],
        )

        summarizer = ResearchWorkspaceConsumerProjectionProvenanceSummarizer()
        summary = summarizer.summarize(report)

        assert summary.covered_output_count == 3
        assert summary.uncovered_output_count == 1


class TestExecutionOutcomeResolver:
    """Test execution outcome resolver."""

    def test_resolve_succeeded(self):
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

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED

    def test_resolve_degraded_from_stages(self):
        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=1,
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

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED

    def test_resolve_degraded_from_stale_sources(self):
        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
            total_duration_ms=100.0,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=2,
            stale_usable_source_count=1,
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

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED

    def test_resolve_degraded_from_expired_sources(self):
        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
            total_duration_ms=100.0,
        )

        freshness = ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=3,
            fresh_source_count=2,
            stale_usable_source_count=0,
            expired_source_count=1,
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

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED

    def test_resolve_degraded_from_budget_skips(self):
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
            admitted_stage_count=2,
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

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED

    def test_resolve_degraded_from_budget_exhaustion(self):
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

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED

    def test_resolve_degraded_from_missing_provenance(self):
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
            covered_output_count=2,
            uncovered_output_count=1,
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        status = resolver.resolve(
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert status == ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED


class TestExecutionReceipt:
    """Test execution receipt model."""

    def test_receipt_creation(self):
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
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        assert receipt.execution_id == "exec-123"
        assert receipt.status == ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED

    def test_receipt_is_immutable(self):
        fingerprint = ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
            value="abc123",
        )

        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name="workspace.bootstrap",
            fingerprint=fingerprint,
        )

        diagnostics = ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=5,
            degraded_stage_count=0,
            reused_resolution_count=0,
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
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        with pytest.raises(Exception):  # Frozen dataclass
            receipt.status = ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED

    def test_receipt_serialization(self):
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
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            identity=identity,
            status=ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED,
            diagnostics=diagnostics,
            freshness=freshness,
            budget=budget,
            provenance=provenance,
        )

        serialized = receipt.to_dict()

        assert serialized["execution_id"] == "exec-123"
        assert serialized["status"] == "succeeded"
        assert "identity" in serialized
        assert "diagnostics" in serialized
        assert "freshness" in serialized
        assert "budget" in serialized
        assert "provenance" in serialized


class TestReceiptBuilder:
    """Test receipt builder."""

    def test_build_receipt(self):
        fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="abc123",
            ),
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="workspace.bootstrap",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        provenance_report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="workspace.bootstrap",
        )

        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder()
        receipt = builder.build(
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        assert receipt.execution_id == "exec-123"
        assert receipt.identity.projection_name == "workspace.bootstrap"
        assert receipt.identity.contract_version == "1.0"

    def test_builder_is_stateless(self):
        # Same inputs should produce equivalent outputs
        fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="abc123",
            ),
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="workspace.bootstrap",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        provenance_report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="workspace.bootstrap",
        )

        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        observed_at = datetime.now(timezone.utc)

        builder = ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder()
        receipt1 = builder.build(
            execution_id="exec-123",
            observed_at=observed_at,
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        receipt2 = builder.build(
            execution_id="exec-123",
            observed_at=observed_at,
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        assert receipt1.execution_id == receipt2.execution_id
        assert receipt1.identity.projection_name == receipt2.identity.projection_name


class TestReceiptVerifier:
    """Test receipt verifier."""

    def test_verify_valid_receipt(self):
        fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="abc123",
            ),
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="workspace.bootstrap",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        provenance_report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="workspace.bootstrap",
        )

        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder()
        receipt = builder.build(
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        verifier = ResearchWorkspaceConsumerProjectionExecutionReceiptVerifier()
        verification_report = verifier.verify(
            receipt=receipt,
            execution_id="exec-123",
            observed_at=receipt.observed_at,
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        assert verification_report.status == ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.VERIFIED
        assert len(verification_report.issues) == 0

    def test_verify_projection_name_mismatch(self):
        fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="abc123",
            ),
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="workspace.bootstrap",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        provenance_report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="workspace.bootstrap",
        )

        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder()
        receipt = builder.build(
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        verifier = ResearchWorkspaceConsumerProjectionExecutionReceiptVerifier()
        verification_report = verifier.verify(
            receipt=receipt,
            execution_id="exec-123",
            observed_at=receipt.observed_at,
            projection_name="workspace.attention",  # Mismatch
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        assert verification_report.status == ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.INVALID
        assert any(
            issue.code == ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.PROJECTION_NAME_MISMATCH
            for issue in verification_report.issues
        )

    def test_verify_fingerprint_mismatch(self):
        fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="abc123",
            ),
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="workspace.bootstrap",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        provenance_report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="workspace.bootstrap",
        )

        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder()
        receipt = builder.build(
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        # Create different fingerprint for verification
        different_fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="def456",  # Different
            ),
        )

        verifier = ResearchWorkspaceConsumerProjectionExecutionReceiptVerifier()
        verification_report = verifier.verify(
            receipt=receipt,
            execution_id="exec-123",
            observed_at=receipt.observed_at,
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=different_fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        assert verification_report.status == ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.INVALID
        assert any(
            issue.code == ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.FINGERPRINT_MISMATCH
            for issue in verification_report.issues
        )

    def test_verifier_is_stateless(self):
        # Verifier should not store state between calls
        fingerprint_snapshot = ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            overall=ResearchWorkspaceConsumerProjectionFingerprint(
                algorithm=ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256,
                value="abc123",
            ),
        )

        diagnostic_report = ResearchWorkspaceConsumerProjectionDiagnosticReport(
            operation_name="workspace.bootstrap",
            status=ResearchWorkspaceConsumerProjectionDiagnosticsStatus.SUCCEEDED,
            duration_ms=100.0,
        )

        provenance_report = ResearchWorkspaceConsumerProjectionProvenanceReport(
            operation_name="workspace.bootstrap",
        )

        budget_snapshot = ResearchWorkspaceConsumerProjectionBudgetSnapshot(
            soft_budget_ms=1000.0,
            elapsed_ms=500.0,
            remaining_ms=500.0,
            overrun_ms=0.0,
            exhausted=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder()
        receipt = builder.build(
            execution_id="exec-123",
            observed_at=datetime.now(timezone.utc),
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        verifier = ResearchWorkspaceConsumerProjectionExecutionReceiptVerifier()

        # First verification
        report1 = verifier.verify(
            receipt=receipt,
            execution_id="exec-123",
            observed_at=receipt.observed_at,
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        # Second verification with same inputs
        report2 = verifier.verify(
            receipt=receipt,
            execution_id="exec-123",
            observed_at=receipt.observed_at,
            projection_name="workspace.bootstrap",
            contract_version="1.0",
            fingerprint_snapshot=fingerprint_snapshot,
            diagnostic_report=diagnostic_report,
            provenance_report=provenance_report,
            budget_snapshot=budget_snapshot,
        )

        assert report1.status == report2.status


class TestVerificationReport:
    """Test verification report model."""

    def test_verification_report_creation(self):
        issue = ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
            code=ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.PROJECTION_NAME_MISMATCH,
            message="Projection name mismatch",
            expected="workspace.bootstrap",
            actual="workspace.attention",
        )

        report = ResearchWorkspaceConsumerProjectionReceiptVerificationReport(
            status=ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.INVALID,
            issues=(issue,),
        )

        assert report.status == ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.INVALID
        assert len(report.issues) == 1

    def test_verification_report_verified(self):
        report = ResearchWorkspaceConsumerProjectionReceiptVerificationReport(
            status=ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.VERIFIED,
            issues=(),
        )

        assert report.status == ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.VERIFIED
        assert len(report.issues) == 0

    def test_verification_report_serialization(self):
        issue = ResearchWorkspaceConsumerProjectionReceiptVerificationIssue(
            code=ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode.PROJECTION_NAME_MISMATCH,
            message="Projection name mismatch",
            expected="workspace.bootstrap",
            actual="workspace.attention",
        )

        report = ResearchWorkspaceConsumerProjectionReceiptVerificationReport(
            status=ResearchWorkspaceConsumerProjectionReceiptVerificationStatus.INVALID,
            issues=(issue,),
        )

        serialized = report.to_dict()

        assert serialized["status"] == "invalid"
        assert len(serialized["issues"]) == 1
        assert serialized["issues"][0]["code"] == "projection_name_mismatch"
