from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionConsumerResponse:
    """
    The final, presentation-ready consumer-facing response for a
    consumer projection's execution readiness.

    Attributes:
        projection_name: Identifies the evaluated projection
        lifecycle_state: Lifecycle state reused from the readiness
            snapshot
        ready_for_execution: Flag reused from the readiness snapshot
        title: Short human-readable label for the lifecycle state
        message: Human-readable explanation of the lifecycle state
    """

    projection_name: str

    lifecycle_state: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState
    )

    ready_for_execution: bool

    title: str

    message: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "lifecycle_state": self.lifecycle_state.value,
            "ready_for_execution": self.ready_for_execution,
            "title": self.title,
            "message": self.message,
        }
