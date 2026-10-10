from .research_workspace_consumer_projection_execution_capability import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
)

from .research_workspace_consumer_projection_execution_capability_reason import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
)

from .research_workspace_consumer_projection_execution_capability_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReport,
)

from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_outcome_report import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionOutcome.READY: (
        ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.READY,
        True,
    ),
    ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING: (
        ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.APPROVAL_REQUIRED,
        False,
    ),
    ResearchWorkspaceConsumerProjectionExecutionOutcome.BLOCKED: (
        ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.EXECUTION_BLOCKED,
        False,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver:
    """
    Resolves a consumer projection's execution outcome into a
    normalized execution capability, using only the execution
    outcome report it is given.

    Does NOT orchestrate execution, schedule work, process
    approvals, access repositories, or inspect the verdict,
    authorization, or any earlier report directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same outcome report always produces the same
        capability report
    - Side-effect free: Never mutates the input outcome report
    """

    def resolve(
        self,
        outcome: ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityReport:
        """
        Resolve a projection execution outcome report into an
        execution capability report.

        Args:
            outcome: The resolved execution outcome report to
                resolve

        Returns:
            An immutable execution capability report
        """

        capability, reason, executable = _RESOLUTIONS[outcome.outcome]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityReport(
            projection_name=outcome.projection_name,
            capability=capability,
            reason=reason,
            executable=executable,
        )
