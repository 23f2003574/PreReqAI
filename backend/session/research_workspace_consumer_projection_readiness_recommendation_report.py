from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_assessment import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
)

from .research_workspace_consumer_projection_readiness_recommendation import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessRecommendationReport:
    """
    Compact, deterministic recommended response posture derived from
    a Commit #7 readiness operational assessment.

    This is advisory only - it does not execute any action, schedule
    remediation, or send a notification.

    Attributes:
        projection_name: Projection name reused from the assessment
        assessment: Assessment reused from the assessment
        recommendation: The resolved response posture
    """

    projection_name: str

    assessment: (
        ResearchWorkspaceConsumerProjectionReadinessAssessment
    )

    recommendation: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation
    )

    @property
    def action_required(self) -> bool:
        return self.recommendation in {
            ResearchWorkspaceConsumerProjectionReadinessRecommendation.REVIEW_CHANGES,
            ResearchWorkspaceConsumerProjectionReadinessRecommendation.INVESTIGATE,
            ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION,
        }

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "assessment": self.assessment.value,
            "recommendation": self.recommendation.value,
            "action_required": self.action_required,
        }
