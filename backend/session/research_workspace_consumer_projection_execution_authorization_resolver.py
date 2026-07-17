from .research_workspace_consumer_projection_execution_authorization import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
)

from .research_workspace_consumer_projection_execution_authorization_reason import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason,
)

from .research_workspace_consumer_projection_execution_authorization_report import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
)

from .research_workspace_consumer_projection_execution_gate_report import (
    ResearchWorkspaceConsumerProjectionExecutionGateReport,
)

from .research_workspace_consumer_projection_execution_gate_status import (
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionGateStatus.OPEN: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorization.AUTHORIZED,
        ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_OPEN,
        True,
    ),
    ResearchWorkspaceConsumerProjectionExecutionGateStatus.CONDITIONAL: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorization.CONDITIONAL,
        ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.APPROVAL_PENDING,
        False,
    ),
    ResearchWorkspaceConsumerProjectionExecutionGateStatus.CLOSED: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorization.DENIED,
        ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_CLOSED,
        False,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver:
    """
    Resolves a consumer projection's execution gate status into a
    policy authorization result, using only the execution gate
    report it is given.

    Does NOT execute projections, schedule work, process approvals,
    access repositories, or inspect readiness, eligibility, or
    execution decisions directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same execution gate report always produces the
        same authorization report
    - Side-effect free: Never mutates the input gate report
    """

    def resolve(
        self,
        gate: ResearchWorkspaceConsumerProjectionExecutionGateReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport:
        """
        Resolve a projection execution gate report into an
        execution authorization report.

        Args:
            gate: The resolved execution gate report to resolve

        Returns:
            An immutable execution authorization report
        """

        authorization, reason, authorized = _RESOLUTIONS[gate.status]

        return ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport(
            projection_name=gate.projection_name,
            authorization=authorization,
            reason=reason,
            authorized=authorized,
        )
