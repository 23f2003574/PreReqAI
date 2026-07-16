from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_reason import (
    ResearchWorkspaceConsumerProjectionReadinessReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessSummary:
    """
    A compact view over a readiness report, for consumers that
    only need the classification, cause, and issue volume.

    Attributes:
        projection_name: Identifies the evaluated projection
        readiness: The overall readiness classification
        reason: The single primary cause of the readiness classification
        issue_count: How many distinct issues were detected
        executable: Whether execution can proceed at all
    """

    projection_name: str

    readiness: (
        ResearchWorkspaceConsumerProjectionReadiness
    )

    reason: (
        ResearchWorkspaceConsumerProjectionReadinessReason
    )

    issue_count: int

    executable: bool

    @property
    def healthy(self) -> bool:
        return (
            self.readiness
            == ResearchWorkspaceConsumerProjectionReadiness.READY
        )

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "readiness": self.readiness.value,
            "reason": self.reason.value,
            "issue_count": self.issue_count,
            "executable": self.executable,
            "healthy": self.healthy,
        }
