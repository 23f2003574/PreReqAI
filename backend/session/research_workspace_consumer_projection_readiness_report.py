from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_issue import (
    ResearchWorkspaceConsumerProjectionReadinessIssue,
)

from .research_workspace_consumer_projection_readiness_reason import (
    ResearchWorkspaceConsumerProjectionReadinessReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessReport:
    """
    The immutable result of evaluating whether a planned
    consumer projection execution is ready to run.

    Attributes:
        projection_name: Identifies the evaluated projection
        readiness: The overall readiness classification
        executable: Whether execution can proceed at all
        reason: The single primary cause of the readiness classification
        issues: Every distinct problem detected during evaluation
    """

    projection_name: str

    readiness: (
        ResearchWorkspaceConsumerProjectionReadiness
    )

    executable: bool

    reason: (
        ResearchWorkspaceConsumerProjectionReadinessReason
    )

    issues: tuple[
        ResearchWorkspaceConsumerProjectionReadinessIssue,
        ...,
    ] = ()

    @property
    def blocked(self) -> bool:
        return (
            self.readiness
            == ResearchWorkspaceConsumerProjectionReadiness.BLOCKED
        )

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "readiness": self.readiness.value,
            "executable": self.executable,
            "reason": self.reason.value,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "blocked": self.blocked,
        }
