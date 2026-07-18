from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage:
    """
    Portable, immutable, consumer-facing package representing the
    final resolved execution capability decision for one projection.

    Captures state only - it does not write logs or persist data.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        decision: Decision reused from the decision snapshot
        executable: Flag reused from the input artifacts
        title: Title reused from the consumer response
        message: Message reused from the consumer response
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
