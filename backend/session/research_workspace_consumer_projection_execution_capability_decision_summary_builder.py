from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_decision_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport,
)

from .research_workspace_consumer_projection_execution_capability_decision_summary import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary,
)


_PRESENTATIONS = {
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT: (
        "Capability Accepted",
        "Projection satisfies execution capability requirements.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW: (
        "Capability Requires Review",
        "Projection requires manual review before execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT: (
        "Capability Rejected",
        "Projection does not satisfy execution capability requirements.",
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder:
    """
    Builds a compact, presentation-ready summary from a consumer
    projection's execution capability decision report.

    Owns only presentation mapping - it does NOT re-run decision
    resolution, re-derive the primary reason, access repositories,
    or inspect the capability snapshot package or any earlier
    report.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same report always produces the same summary
    - Side-effect free: Never mutates the input report
    """

    def build(
        self,
        decision: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary:
        """
        Build a decision summary from an execution capability
        decision report.

        Args:
            decision: The resolved execution capability decision
                report to summarize

        Returns:
            An immutable, compact decision summary
        """

        title, description = _PRESENTATIONS[decision.decision]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary(
            projection_name=decision.projection_name,
            decision=decision.decision,
            reason=decision.reason,
            title=title,
            description=description,
            executable=decision.executable,
        )
