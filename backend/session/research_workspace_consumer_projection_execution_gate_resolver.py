from .research_workspace_consumer_projection_execution_decision import (
    ResearchWorkspaceConsumerProjectionExecutionDecision,
)

from .research_workspace_consumer_projection_execution_decision_report import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
)

from .research_workspace_consumer_projection_execution_gate_reason import (
    ResearchWorkspaceConsumerProjectionExecutionGateReason,
)

from .research_workspace_consumer_projection_execution_gate_report import (
    ResearchWorkspaceConsumerProjectionExecutionGateReport,
)

from .research_workspace_consumer_projection_execution_gate_status import (
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionDecision.EXECUTE: (
        ResearchWorkspaceConsumerProjectionExecutionGateStatus.OPEN,
        ResearchWorkspaceConsumerProjectionExecutionGateReason.EXECUTION_ALLOWED,
        True,
    ),
    ResearchWorkspaceConsumerProjectionExecutionDecision.WAIT_FOR_APPROVAL: (
        ResearchWorkspaceConsumerProjectionExecutionGateStatus.CONDITIONAL,
        ResearchWorkspaceConsumerProjectionExecutionGateReason.APPROVAL_REQUIRED,
        False,
    ),
    ResearchWorkspaceConsumerProjectionExecutionDecision.DO_NOT_EXECUTE: (
        ResearchWorkspaceConsumerProjectionExecutionGateStatus.CLOSED,
        ResearchWorkspaceConsumerProjectionExecutionGateReason.EXECUTION_BLOCKED,
        False,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionGateResolver:
    """
    Resolves a consumer projection's execution decision into a
    final gate permission, using only the execution decision report
    it is given.

    Does NOT execute projections, schedule work, process approvals,
    access repositories, or inspect readiness or eligibility
    directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same execution decision report always produces
        the same gate report
    - Side-effect free: Never mutates the input decision report
    """

    def resolve(
        self,
        decision: ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionGateReport:
        """
        Resolve a projection execution decision report into an
        execution gate report.

        Args:
            decision: The resolved execution decision report to
                resolve

        Returns:
            An immutable execution gate report
        """

        status, reason, can_continue = _RESOLUTIONS[decision.decision]

        return ResearchWorkspaceConsumerProjectionExecutionGateReport(
            projection_name=decision.projection_name,
            status=status,
            reason=reason,
            can_continue=can_continue,
        )
