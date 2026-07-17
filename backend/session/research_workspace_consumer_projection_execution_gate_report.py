from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_gate_reason import (
    ResearchWorkspaceConsumerProjectionExecutionGateReason,
)

from .research_workspace_consumer_projection_execution_gate_status import (
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionGateReport:
    """
    The immutable result of resolving a consumer projection's
    execution decision into a final gate permission, the last
    decision boundary before any execution subsystem.

    Attributes:
        projection_name: Identifies the evaluated projection
        status: The resolved execution gate status
        reason: The primary cause of the gate status
        can_continue: Whether execution may proceed right now
    """

    projection_name: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionGateStatus
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionGateReason
    )

    can_continue: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "status": self.status.value,
            "reason": self.reason.value,
            "can_continue": self.can_continue,
        }
