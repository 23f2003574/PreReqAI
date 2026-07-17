from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
)

from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionDecisionPackage:
    """
    Portable, immutable bundle of the complete execution decision
    for one projection, the final execution-domain artifact exposed
    to downstream consumers.

    Combines the Commit #8 execution snapshot and Commit #12
    consumer response into one flat result that a future API,
    logging adapter, or dashboard can consume without traversing
    the earlier readiness, eligibility, gate, authorization,
    verdict, outcome, or lifecycle reports.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        lifecycle_state: Lifecycle state reused from the consumer response
        outcome: Outcome reused from the execution snapshot
        ready_for_execution: Flag reused from the execution snapshot
        title: Title reused from the consumer response
        message: Message reused from the consumer response
    """

    projection_name: str

    lifecycle_state: (
        ResearchWorkspaceConsumerProjectionExecutionLifecycleState
    )

    outcome: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome
    )

    ready_for_execution: bool

    title: str

    message: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "lifecycle_state": self.lifecycle_state.value,
            "outcome": self.outcome.value,
            "ready_for_execution": self.ready_for_execution,
            "title": self.title,
            "message": self.message,
        }
