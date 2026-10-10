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
class ResearchWorkspaceConsumerProjectionExecutionOutcomeReport:
    """
    The immutable result of resolving a consumer projection's
    execution verdict into the final normalized execution state
    exposed to downstream consumers.

    Attributes:
        projection_name: Identifies the evaluated projection
        outcome: The resolved execution outcome
        reason: The primary cause of the outcome
        ready_for_execution: Whether execution is ready to proceed
            right now
    """

    projection_name: str

    outcome: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionOutcomeReason
    )

    ready_for_execution: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "ready_for_execution": self.ready_for_execution,
        }
