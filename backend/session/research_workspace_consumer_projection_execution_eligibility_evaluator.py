from .research_workspace_consumer_projection_execution_eligibility import (
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
)

from .research_workspace_consumer_projection_execution_eligibility_reason import (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason,
)

from .research_workspace_consumer_projection_execution_eligibility_report import (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
)

from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_report import (
    ResearchWorkspaceConsumerProjectionReadinessReport,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionReadiness.READY: (
        ResearchWorkspaceConsumerProjectionExecutionEligibility.ELIGIBLE,
        ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.READY,
    ),
    ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY: (
        ResearchWorkspaceConsumerProjectionExecutionEligibility.CONDITIONALLY_ELIGIBLE,
        ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.DEGRADED_READY,
    ),
    ResearchWorkspaceConsumerProjectionReadiness.BLOCKED: (
        ResearchWorkspaceConsumerProjectionExecutionEligibility.INELIGIBLE,
        ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.BLOCKED,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator:
    """
    Determines whether a consumer projection is eligible for
    execution, using only the readiness report it is given.

    Does NOT execute projections, schedule work, evaluate approval
    workflows, or access repositories.

    The evaluator is:
    - Stateless: No instance state
    - Deterministic: Same readiness report always produces the
        same eligibility report
    - Side-effect free: Never mutates the input readiness report
    """

    def evaluate(
        self,
        readiness: ResearchWorkspaceConsumerProjectionReadinessReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionEligibilityReport:
        """
        Evaluate a projection readiness report for execution
        eligibility.

        Args:
            readiness: The resolved readiness report to evaluate

        Returns:
            An immutable execution eligibility report
        """

        eligibility, reason = _RESOLUTIONS[readiness.readiness]

        return ResearchWorkspaceConsumerProjectionExecutionEligibilityReport(
            projection_name=readiness.projection_name,
            eligibility=eligibility,
            reason=reason,
            executable=readiness.executable,
        )
