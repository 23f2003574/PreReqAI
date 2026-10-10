from .research_workspace_consumer_projection_execution_decision import (
    ResearchWorkspaceConsumerProjectionExecutionDecision,
)

from .research_workspace_consumer_projection_execution_decision_reason import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason,
)

from .research_workspace_consumer_projection_execution_decision_report import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
)

from .research_workspace_consumer_projection_execution_eligibility import (
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
)

from .research_workspace_consumer_projection_execution_eligibility_report import (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionEligibility.ELIGIBLE: (
        ResearchWorkspaceConsumerProjectionExecutionDecision.EXECUTE,
        ResearchWorkspaceConsumerProjectionExecutionDecisionReason.ELIGIBLE,
    ),
    ResearchWorkspaceConsumerProjectionExecutionEligibility.CONDITIONALLY_ELIGIBLE: (
        ResearchWorkspaceConsumerProjectionExecutionDecision.WAIT_FOR_APPROVAL,
        ResearchWorkspaceConsumerProjectionExecutionDecisionReason.CONDITIONAL,
    ),
    ResearchWorkspaceConsumerProjectionExecutionEligibility.INELIGIBLE: (
        ResearchWorkspaceConsumerProjectionExecutionDecision.DO_NOT_EXECUTE,
        ResearchWorkspaceConsumerProjectionExecutionDecisionReason.BLOCKED,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionDecisionResolver:
    """
    Resolves a consumer projection's execution eligibility into a
    concrete next-step decision, using only the eligibility report
    it is given.

    Does NOT execute projections, schedule work, evaluate approval
    workflows, access repositories, or inspect readiness directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same eligibility report always produces the
        same decision report
    - Side-effect free: Never mutates the input eligibility report
    """

    def resolve(
        self,
        eligibility: ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionDecisionReport:
        """
        Resolve a projection execution eligibility report into an
        execution decision.

        Args:
            eligibility: The resolved eligibility report to resolve

        Returns:
            An immutable execution decision report
        """

        decision, reason = _RESOLUTIONS[eligibility.eligibility]

        return ResearchWorkspaceConsumerProjectionExecutionDecisionReport(
            projection_name=eligibility.projection_name,
            decision=decision,
            reason=reason,
            executable=eligibility.executable,
        )
