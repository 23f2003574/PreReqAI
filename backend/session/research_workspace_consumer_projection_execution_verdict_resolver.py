from .research_workspace_consumer_projection_execution_authorization import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
)

from .research_workspace_consumer_projection_execution_authorization_report import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
)

from .research_workspace_consumer_projection_execution_verdict import (
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
)

from .research_workspace_consumer_projection_execution_verdict_reason import (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason,
)

from .research_workspace_consumer_projection_execution_verdict_report import (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.AUTHORIZED: (
        ResearchWorkspaceConsumerProjectionExecutionVerdict.APPROVED,
        ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZED,
        True,
    ),
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.CONDITIONAL: (
        ResearchWorkspaceConsumerProjectionExecutionVerdict.PENDING,
        ResearchWorkspaceConsumerProjectionExecutionVerdictReason.APPROVAL_REQUIRED,
        False,
    ),
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.DENIED: (
        ResearchWorkspaceConsumerProjectionExecutionVerdict.REJECTED,
        ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZATION_DENIED,
        False,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionVerdictResolver:
    """
    Resolves a consumer projection's execution authorization into
    the final policy verdict, using only the authorization report
    it is given.

    Does NOT execute projections, schedule work, process approvals,
    access repositories, or inspect the execution gate or any
    earlier report directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same authorization report always produces the
        same verdict report
    - Side-effect free: Never mutates the input authorization report
    """

    def resolve(
        self,
        authorization: ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionVerdictReport:
        """
        Resolve a projection execution authorization report into an
        execution verdict report.

        Args:
            authorization: The resolved execution authorization
                report to resolve

        Returns:
            An immutable execution verdict report
        """

        verdict, reason, approved = _RESOLUTIONS[
            authorization.authorization
        ]

        return ResearchWorkspaceConsumerProjectionExecutionVerdictReport(
            projection_name=authorization.projection_name,
            verdict=verdict,
            reason=reason,
            approved=approved,
        )
