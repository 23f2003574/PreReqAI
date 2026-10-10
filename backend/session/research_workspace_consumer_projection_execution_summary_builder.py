from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_outcome_report import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
)

from .research_workspace_consumer_projection_execution_summary import (
    ResearchWorkspaceConsumerProjectionExecutionSummary,
)


_PRESENTATIONS = {
    ResearchWorkspaceConsumerProjectionExecutionOutcome.READY: (
        "Ready for Execution",
        "Projection is approved and may proceed.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING: (
        "Approval Required",
        "Projection is awaiting approval before execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionOutcome.BLOCKED: (
        "Execution Blocked",
        "Projection cannot proceed to execution.",
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder:
    """
    Builds a compact, presentation-ready summary from a consumer
    projection's execution outcome report.

    Owns only presentation mapping - it does NOT re-run outcome
    resolution, re-derive the primary reason, access repositories,
    or inspect the execution verdict, authorization, or any earlier
    report.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same report always produces the same summary
    - Side-effect free: Never mutates the input report
    """

    def build(
        self,
        outcome: ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionSummary:
        """
        Build an execution summary from an execution outcome report.

        Args:
            outcome: The resolved execution outcome report to
                summarize

        Returns:
            An immutable, compact execution summary
        """

        title, description = _PRESENTATIONS[outcome.outcome]

        return ResearchWorkspaceConsumerProjectionExecutionSummary(
            projection_name=outcome.projection_name,
            outcome=outcome.outcome,
            reason=outcome.reason,
            title=title,
            description=description,
            ready_for_execution=outcome.ready_for_execution,
        )
