from .research_workspace_consumer_projection_execution_lifecycle_reason import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason,
)

from .research_workspace_consumer_projection_execution_lifecycle_report import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReport,
)

from .research_workspace_consumer_projection_execution_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
)

from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_outcome_report import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
)


_RESOLUTIONS = {
    ResearchWorkspaceConsumerProjectionExecutionOutcome.READY: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState.READY,
        ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.READY_FOR_EXECUTION,
        True,
    ),
    ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState.WAITING,
        ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.WAITING_FOR_APPROVAL,
        False,
    ),
    ResearchWorkspaceConsumerProjectionExecutionOutcome.BLOCKED: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState.BLOCKED,
        ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.EXECUTION_BLOCKED,
        False,
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver:
    """
    Resolves a consumer projection's execution outcome into a
    normalized lifecycle state, using only the execution outcome
    report it is given.

    Does NOT orchestrate execution, schedule work, process
    approvals, access repositories, or inspect the verdict,
    authorization, or any earlier report directly.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same outcome report always produces the same
        lifecycle report
    - Side-effect free: Never mutates the input outcome report
    """

    def resolve(
        self,
        outcome: ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
    ) -> ResearchWorkspaceConsumerProjectionExecutionLifecycleReport:
        """
        Resolve a projection execution outcome report into an
        execution lifecycle report.

        Args:
            outcome: The resolved execution outcome report to
                resolve

        Returns:
            An immutable execution lifecycle report
        """

        state, reason, active = _RESOLUTIONS[outcome.outcome]

        return ResearchWorkspaceConsumerProjectionExecutionLifecycleReport(
            projection_name=outcome.projection_name,
            state=state,
            reason=reason,
            active=active,
        )
