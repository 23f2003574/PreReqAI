from .research_workspace_consumer_projection_execution_health import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
)

from .research_workspace_consumer_projection_execution_health_summary import (
    ResearchWorkspaceConsumerProjectionExecutionHealthSummary,
)

from .research_workspace_consumer_projection_quality_signal_report import (
    ResearchWorkspaceConsumerProjectionQualitySignalReport,
)

from .research_workspace_consumer_projection_quality_signal_severity import (
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


class ResearchWorkspaceConsumerProjectionExecutionHealthSummarizer:
    """
    Reduces a quality signal report (Commit #2) into a compact
    overall health classification.

    The summarizer works entirely from the already-extracted quality
    signals. It does NOT inspect the execution receipt, diagnostics,
    freshness, budget state, provenance graph, or projection payload -
    those decisions already happened in the quality signal extractor.
    This preserves the dependency chain:

        Execution Receipt
              -> Quality Signal Extractor
              -> Quality Signal Report
              -> Health Summarizer
              -> Health Summary

    The summarizer is:
    - Stateless: No instance state
    - Deterministic: Same report always produces the same summary
    - Side-effect free: Never mutates the report
    """

    def summarize(
        self,
        report: (
            ResearchWorkspaceConsumerProjectionQualitySignalReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionHealthSummary:
        """
        Summarize a quality signal report into an execution health summary.

        Args:
            report: The quality signal report to reduce

        Returns:
            An immutable, deterministic execution health summary
        """

        warning_count = sum(
            1
            for signal in report.signals
            if signal.severity
            == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING
        )

        critical_count = sum(
            1
            for signal in report.signals
            if signal.severity
            == ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL
        )

        # Critical always takes precedence; an info-only report (no
        # warnings, no critical signals) is still HEALTHY.
        if critical_count > 0:
            health = (
                ResearchWorkspaceConsumerProjectionExecutionHealth.CRITICAL
            )
        elif warning_count > 0:
            health = (
                ResearchWorkspaceConsumerProjectionExecutionHealth.ATTENTION
            )
        else:
            health = (
                ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY
            )

        return ResearchWorkspaceConsumerProjectionExecutionHealthSummary(
            execution_id=report.execution_id,
            projection_name=report.projection_name,
            health=health,
            signal_count=len(report.signals),
            warning_count=warning_count,
            critical_count=critical_count,
        )
