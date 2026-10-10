from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponse:
    """
    The final, presentation-ready consumer-facing response for a
    consumer projection's execution capability decision.

    Attributes:
        projection_name: Identifies the evaluated projection
        decision: Decision reused from the decision snapshot
        executable: Flag reused from the decision snapshot
        title: Short human-readable label for the decision
        message: Human-readable explanation of the decision
    """

    projection_name: str

    decision: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision
    )

    executable: bool

    title: str

    message: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "decision": self.decision.value,
            "executable": self.executable,
            "title": self.title,
            "message": self.message,
        }
