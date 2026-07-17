from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_outcome_reason import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
)

from .research_workspace_consumer_projection_execution_outcome_report import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
)

from .research_workspace_consumer_projection_execution_verdict import (
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
)

from .research_workspace_consumer_projection_execution_verdict_report import (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionVerdict.APPROVED: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome.READY,
        ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_APPROVED,
        True,
    ),
    ResearchWorkspaceConsumerProjectionExecutionVerdict.PENDING: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING,
        ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.APPROVAL_PENDING,
        False,
    ),
    ResearchWorkspaceConsumerProjectionExecutionVerdict.REJECTED: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome.BLOCKED,
        ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_REJECTED,
        False,
    ),
}


class ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver:
    """
    Resolves a consumer projection's execution verdict into the
    final normalized execution state, using only the verdict report
    it is given.

    Named for what it consumes (a verdict) rather than
    `...ExecutionOutcomeResolver`, since that name is already taken
    by the unrelated receipt-summary outcome resolver in
    `research_workspace_consumer_projection_execution_outcome_resolver.py`.

    Does NOT execute projections, schedule work, process approvals,
    access repositories, or inspect authorization or any earlier
    report directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same verdict report always produces the same
        outcome report
    - Side-effect free: Never mutates the input verdict report
    """

    def resolve(
        self,
        verdict: ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionOutcomeReport:
        """
        Resolve a projection execution verdict report into an
        execution outcome report.

        Args:
            verdict: The resolved execution verdict report to
                resolve

        Returns:
            An immutable execution outcome report
        """

        outcome, reason, ready_for_execution = _RESOLUTIONS[
            verdict.verdict
        ]

        return ResearchWorkspaceConsumerProjectionExecutionOutcomeReport(
            projection_name=verdict.projection_name,
            outcome=outcome,
            reason=reason,
            ready_for_execution=ready_for_execution,
        )
