from .research_workspace_consumer_projection_execution_capability_consumer_response import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse,
)

from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_decision_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot,
)


_PRESENTATIONS = {
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT: (
        "Capability Accepted",
        "Projection satisfies all execution capability requirements.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW: (
        "Capability Requires Review",
        "Projection requires manual review before execution.",
    ),
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT: (
        "Capability Rejected",
        "Projection cannot proceed because execution capability "
        "requirements are not satisfied.",
    ),
}


class ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder:
    """
    Builds the final consumer-facing execution capability response
    from a consumer projection's execution capability decision
    snapshot.

    Owns only presentation mapping - it does NOT re-run decision
    resolution, recalculate the snapshot, access repositories, or
    inspect any earlier report.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same snapshot always produces the same response
    - Side-effect free: Never mutates the input snapshot
    """

    def build(
        self,
        snapshot: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse:
        """
        Build a consumer response from an execution capability
        decision snapshot.

        Args:
            snapshot: The execution capability decision snapshot to
                present

        Returns:
            An immutable, consumer-facing execution capability
            response
        """

        title, message = _PRESENTATIONS[snapshot.decision]

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse(
            projection_name=snapshot.projection_name,
            decision=snapshot.decision,
            executable=snapshot.executable,
            title=title,
            message=message,
        )
