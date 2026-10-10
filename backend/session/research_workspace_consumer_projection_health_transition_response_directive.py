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
class ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective:
    """
    Finalized, immutable advisory response decision combining a
    Commit #8 response recommendation and a Commit #9 response
    priority result.

    This is a portable description of a decision, not an action -
    it does not create a task, send an alert, trigger a retry, or
    perform remediation. It carries no timestamp, mutable status,
    acknowledgement state, completion state, assigned user, or retry
    counter; those belong to future workflow or persistence layers.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        previous_execution_id: Execution ID reused from the input artifacts
        current_execution_id: Execution ID reused from the input artifacts
        recommendation: Recommendation kind reused from the recommendation
        priority: Response priority reused from the priority result
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
    def action_recommended(self) -> bool:
        # Mirrors the authoritative semantics already defined on
        # ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation
        # (Commit #8) - action requirement is derived from the
        # recommendation, never from priority alone.
        return self.recommendation not in {
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.CONTINUE_OBSERVATION,
        }

    def to_dict(self):
        """
        Serialize the response directive to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "action_recommended": self.action_recommended,
        }
