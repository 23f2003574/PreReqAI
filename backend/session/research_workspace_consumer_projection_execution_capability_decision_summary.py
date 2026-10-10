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
class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary:
    """
    A compact, presentation-ready summary of a consumer projection's
    execution capability decision, for fast consumer inspection.

    Attributes:
        projection_name: Identifies the evaluated projection
        decision: Decision reused from the capability decision report
        reason: Reason reused from the capability decision report
        title: Short human-readable label for the decision
        description: Human-readable explanation of the decision
        executable: Flag reused from the capability decision report
    """

    projection_name: str

    decision: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason
    )

    title: str

    description: str

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "decision": self.decision.value,
            "reason": self.reason.value,
            "title": self.title,
            "description": self.description,
            "executable": self.executable,
        }
