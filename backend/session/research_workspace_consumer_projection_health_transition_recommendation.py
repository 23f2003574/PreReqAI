from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_health_transition_assessment_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
)

from .research_workspace_consumer_projection_health_transition_recommendation_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation:
    """
    Compact, deterministic recommended response posture derived from
    a Commit #7 operational assessment.

    This is advisory only - it does not execute any action, schedule
    remediation, or send a notification.

    Attributes:
        projection_name: Projection name reused from the assessment
        previous_execution_id: Execution ID reused from the assessment
        current_execution_id: Execution ID reused from the assessment
        assessment: Assessment kind reused from the assessment
        recommendation: The resolved response posture
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    assessment: (
        ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind
    )

    recommendation: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind
    )

    @property
    def action_recommended(self) -> bool:
        return self.recommendation not in {
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.CONTINUE_OBSERVATION,
        }

    def to_dict(self):
        """
        Serialize the recommendation to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "assessment": self.assessment.value,
            "recommendation": self.recommendation.value,
            "action_recommended": self.action_recommended,
        }
