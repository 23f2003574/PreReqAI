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
class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport:
    """
    The immutable result of resolving a consumer projection's
    execution capability snapshot package into a normalized policy
    decision, exposed to downstream consumers.

    Attributes:
        projection_name: Identifies the evaluated projection
        decision: The resolved capability decision
        reason: The primary cause of the decision
        executable: Flag reused from the capability snapshot package
    """

    projection_name: str

    decision: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason
    )

    executable: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "decision": self.decision.value,
            "reason": self.reason.value,
            "executable": self.executable,
        }
