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
class ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot:
    """
    Compact, immutable, consumer-facing read model of a consumer
    projection's execution readiness.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        lifecycle_state: Lifecycle state reused from the lifecycle report
        reason: Reason reused from the lifecycle report
        ready_for_execution: Mapped from the lifecycle report's
            active flag
        summary: Human-readable summary reused from the execution
            summary's description
    """

    projection_name: str

    lifecycle_state: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleReason
    )

    ready_for_execution: bool

    summary: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "lifecycle_state": self.lifecycle_state.value,
            "reason": self.reason.value,
            "ready_for_execution": self.ready_for_execution,
            "summary": self.summary,
        }
