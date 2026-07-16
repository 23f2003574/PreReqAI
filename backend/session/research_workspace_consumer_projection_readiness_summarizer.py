from .research_workspace_consumer_projection_readiness_report import (
    ResearchWorkspaceConsumerProjectionReadinessReport,
)

from .research_workspace_consumer_projection_readiness_summary import (
    ResearchWorkspaceConsumerProjectionReadinessSummary,
)


class ResearchWorkspaceConsumerProjectionReadinessSummarizer:
    """
    Reduces a readiness report (Commit #1/#2) to a compact summary
    for fast consumer inspection.

    Owns only aggregation - it does NOT re-run readiness evaluation,
    re-derive the primary reason, access repositories, or read the
    clock. Every field is either copied directly from the report or
    derived from data already on it.

    The summarizer is:
    - Stateless: No instance state
    - Deterministic: Same report always produces the same summary
    - Side-effect free: Never mutates the input report
    """

    def summarize(
        self,
        report: (
            ResearchWorkspaceConsumerProjectionReadinessReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessSummary:
        """
        Summarize a readiness report.

        Args:
            report: The readiness report to summarize

        Returns:
            An immutable, compact readiness summary
        """

        return ResearchWorkspaceConsumerProjectionReadinessSummary(
            projection_name=report.projection_name,
            readiness=report.readiness,
            reason=report.reason,
            issue_count=len(report.issues),
            executable=report.executable,
        )
