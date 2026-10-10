from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_priority import (
    ResearchWorkspaceConsumerProjectionReadinessPriority,
)

from .research_workspace_consumer_projection_readiness_recommendation import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessPriorityReport:
    """
    Compact, deterministic relative response priority derived from
    a Commit #8 readiness recommendation.

    This is a classification only - it does not schedule, queue,
    notify, or execute anything.

    Attributes:
        projection_name: Projection name reused from the recommendation
        recommendation: Recommendation reused from the recommendation
        priority: The resolved relative response priority
    """

    projection_name: str

    recommendation: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation
    )

    priority: (
        ResearchWorkspaceConsumerProjectionReadinessPriority
    )

    @property
    def prioritized(self) -> bool:
        return self.priority not in {
            ResearchWorkspaceConsumerProjectionReadinessPriority.NONE,
            ResearchWorkspaceConsumerProjectionReadinessPriority.LOW,
        }

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "prioritized": self.prioritized,
        }
