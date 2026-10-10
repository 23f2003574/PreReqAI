from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_decision_reason import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot:
    """
    Compact, immutable, consumer-facing read model of a consumer
    projection's execution capability decision.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        decision: Decision reused from the decision report
        reason: Reason reused from the decision report
        executable: Flag reused from the decision report
        title: Title reused from the decision summary
        description: Description reused from the decision summary
    """

    projection_name: str

    decision: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason
    )

    executable: bool

    title: str

    description: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "decision": self.decision.value,
            "reason": self.reason.value,
            "executable": self.executable,
            "title": self.title,
            "description": self.description,
        }
