from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_outcome_reason import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionSummary:
    """
    A compact, presentation-ready summary of a consumer projection's
    execution outcome, for fast consumer inspection.

    Attributes:
        projection_name: Identifies the evaluated projection
        outcome: Outcome reused from the execution outcome report
        reason: Reason reused from the execution outcome report
        title: Short human-readable label for the outcome
        description: Human-readable explanation of the outcome
        ready_for_execution: Flag reused from the execution outcome
            report
    """

    projection_name: str

    outcome: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionOutcomeReason
    )

    title: str

    description: str

    ready_for_execution: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "title": self.title,
            "description": self.description,
            "ready_for_execution": self.ready_for_execution,
        }
