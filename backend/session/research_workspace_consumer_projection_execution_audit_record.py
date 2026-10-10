from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_authorization import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
)

from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_verdict import (
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionAuditRecord:
    """
    Portable, immutable audit record representing the final
    execution decision chain for one projection, for downstream
    logging or persistence layers.

    Captures state only - it does not write logs or persist data.

    Attributes:
        projection_name: Projection name reused from the snapshot
        outcome: Outcome reused from the snapshot
        verdict: Verdict reused from the snapshot
        authorization: Authorization reused from the snapshot
        ready_for_execution: Flag reused from the snapshot
        summary: Human-readable summary reused from the snapshot's
            description
    """

    projection_name: str

    outcome: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome
    )

    verdict: (
        ResearchWorkspaceConsumerProjectionExecutionVerdict
    )

    authorization: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorization
    )

    ready_for_execution: bool

    summary: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "outcome": self.outcome.value,
            "verdict": self.verdict.value,
            "authorization": self.authorization.value,
            "ready_for_execution": self.ready_for_execution,
            "summary": self.summary,
        }
