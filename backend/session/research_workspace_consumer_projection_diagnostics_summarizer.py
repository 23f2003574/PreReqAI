from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)

from .research_workspace_consumer_projection_diagnostic_status import (
    ResearchWorkspaceConsumerProjectionDiagnosticStatus,
)

from .research_workspace_consumer_projection_diagnostics_summary import (
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
)


class ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer:
    """
    Derives compact diagnostics summary from finalized diagnostic report.

    This pure summarizer is used by both the receipt builder and the
    receipt verifier to ensure consistent summary derivation from the
    same finalized artifacts.

    Does not recompute diagnostics or call any services.
    Simply summarizes the existing finalized report.
    """

    def summarize(
        self,
        report: (
            ResearchWorkspaceConsumerProjectionDiagnosticReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionDiagnosticsSummary:
        """
        Derive a compact summary from the finalized diagnostic report.

        Args:
            report: The finalized diagnostic report

        Returns:
            Compact summary of execution diagnostics
        """

        stage_count = len(report.stages)

        degraded_stage_count = sum(
            1
            for stage in report.stages
            if stage.status
            == ResearchWorkspaceConsumerProjectionDiagnosticStatus.DEGRADED
        )

        reused_resolution_count = sum(
            input_diagnostic.reuse_count
            for input_diagnostic in report.inputs
        )

        return ResearchWorkspaceConsumerProjectionDiagnosticsSummary(
            stage_count=stage_count,
            degraded_stage_count=degraded_stage_count,
            reused_resolution_count=reused_resolution_count,
            total_duration_ms=report.duration_ms,
        )
