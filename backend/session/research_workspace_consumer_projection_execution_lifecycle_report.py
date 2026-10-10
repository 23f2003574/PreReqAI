from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_lifecycle_reason import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason,
)

from .research_workspace_consumer_projection_execution_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionLifecycleReport:
    """
    The immutable result of resolving a consumer projection's
    execution outcome into a normalized lifecycle state, exposed to
    downstream orchestration.

    Attributes:
        projection_name: Identifies the evaluated projection
        state: The resolved lifecycle state
        reason: The primary cause of the lifecycle state
        active: Whether the projection is actively ready for
            execution right now
    """

    projection_name: str

    state: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleReason
    )

    active: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "state": self.state.value,
            "reason": self.reason.value,
            "active": self.active,
        }
