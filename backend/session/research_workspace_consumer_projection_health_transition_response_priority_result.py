from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_health_transition_recommendation_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
)

from .research_workspace_consumer_projection_health_transition_response_priority import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult:
    """
    Compact, deterministic relative response priority derived from
    a Commit #8 response recommendation.

    This is a classification only - it does not schedule, queue,
    notify, or execute anything.

    Attributes:
        projection_name: Projection name reused from the recommendation
        previous_execution_id: Execution ID reused from the recommendation
        current_execution_id: Execution ID reused from the recommendation
        recommendation: Recommendation kind reused from the recommendation
        priority: The resolved relative response priority
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    recommendation: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind
    )

    priority: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority
    )

    @property
    def prioritized(self) -> bool:
        return self.priority not in {
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE,
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.LOW,
        }

    def to_dict(self):
        """
        Serialize the response priority result to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "prioritized": self.prioritized,
        }
