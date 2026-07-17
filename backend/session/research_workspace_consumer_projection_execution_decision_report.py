from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_decision import (
    ResearchWorkspaceConsumerProjectionExecutionDecision,
)

from .research_workspace_consumer_projection_execution_decision_reason import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionDecisionReport:
    """
    The immutable result of resolving a consumer projection's
    execution eligibility into a concrete next-step decision.

    Attributes:
        projection_name: Identifies the evaluated projection
        decision: The resolved execution decision
        reason: The primary cause of the decision
        executable: Whether execution can proceed at all, carried
            forward unchanged from the eligibility report
    """

    projection_name: str

    decision: (
        ResearchWorkspaceConsumerProjectionExecutionDecision
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionDecisionReason
    )

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "decision": self.decision.value,
            "reason": self.reason.value,
            "executable": self.executable,
        }
