from .research_workspace_consumer_projection_execution_consumer_response import (
    ResearchWorkspaceConsumerProjectionExecutionConsumerResponse,
)

from .research_workspace_consumer_projection_execution_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
)

from .research_workspace_consumer_projection_execution_readiness_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot,
)


_PRESENTATIONS = {
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState.READY: (
        "Ready for Execution",
        "Projection is ready to execute.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState.WAITING: (
        "Awaiting Approval",
        "Projection is waiting for approval before execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState.BLOCKED: (
        "Execution Blocked",
        "Projection is not eligible for execution.",
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder:
    """
    Builds the final consumer-facing execution response from a
    consumer projection's execution readiness snapshot.

    Owns only presentation mapping - it does NOT re-run lifecycle
    resolution, recalculate readiness, access repositories, or
    inspect any earlier report.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same snapshot always produces the same response
    - Side-effect free: Never mutates the input snapshot
    """

    def build(
        self,
        snapshot: ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot,
    ) -> ResearchWorkspaceConsumerProjectionExecutionConsumerResponse:
        """
        Build a consumer response from an execution readiness
        snapshot.

        Args:
            snapshot: The execution readiness snapshot to present

        Returns:
            An immutable, consumer-facing execution response
        """

        title, message = _PRESENTATIONS[snapshot.lifecycle_state]

        return ResearchWorkspaceConsumerProjectionExecutionConsumerResponse(
            projection_name=snapshot.projection_name,
            lifecycle_state=snapshot.lifecycle_state,
            ready_for_execution=snapshot.ready_for_execution,
            title=title,
            message=message,
        )
