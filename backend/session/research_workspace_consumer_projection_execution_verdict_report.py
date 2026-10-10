from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_verdict import (
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
)

from .research_workspace_consumer_projection_execution_verdict_reason import (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionVerdictReport:
    """
    The immutable result of resolving a consumer projection's
    execution authorization into the final policy verdict, before
    any execution engine.

    Attributes:
        projection_name: Identifies the evaluated projection
        verdict: The resolved execution verdict
        reason: The primary cause of the verdict
        approved: Whether execution is approved right now
    """

    projection_name: str

    verdict: (
        ResearchWorkspaceConsumerProjectionExecutionVerdict
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionVerdictReason
    )

    approved: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "verdict": self.verdict.value,
            "reason": self.reason.value,
            "approved": self.approved,
        }
