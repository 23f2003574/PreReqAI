from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_impact import (
    ResearchWorkspaceConsumerProjectionReadinessImpact,
)

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessImpactSummary:
    """
    Compact, deterministic aggregate of the issue-level changes
    described by a Commit #5 readiness transition explanation.

    Attributes:
        projection_name: Projection name reused from the explanation
        transition: Readiness transition reused from the explanation
        impact: Directional classification of the issue-level change
        appeared_count: Number of newly appeared issue codes
        resolved_count: Number of resolved issue codes
        persistent_count: Number of persistent issue codes
    """

    projection_name: str

    transition: (
        ResearchWorkspaceConsumerProjectionReadinessTransition
    )

    impact: (
        ResearchWorkspaceConsumerProjectionReadinessImpact
    )

    appeared_count: int

    resolved_count: int

    persistent_count: int

    @property
    def changed_count(self) -> int:
        return (
            self.appeared_count
            + self.resolved_count
        )

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "transition": self.transition.value,
            "impact": self.impact.value,
            "appeared_count": self.appeared_count,
            "resolved_count": self.resolved_count,
            "persistent_count": self.persistent_count,
            "changed_count": self.changed_count,
        }
