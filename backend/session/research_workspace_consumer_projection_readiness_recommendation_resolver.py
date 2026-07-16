from .research_workspace_consumer_projection_readiness_assessment import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
)

from .research_workspace_consumer_projection_readiness_assessment_report import (
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
)

from .research_workspace_consumer_projection_readiness_recommendation import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
)

from .research_workspace_consumer_projection_readiness_recommendation_report import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendationReport,
)


# Direct, static mapping from operational assessment to recommended
# response posture - deliberately not a nested conditional.
_RECOMMENDATIONS = {
    ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation.CONTINUE_MONITORING
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation.REVIEW_CHANGES
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation.INVESTIGATE
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION
    ),
}


class ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver:
    """
    Resolves a Commit #7 readiness operational assessment into a
    generic recommended response posture.

    The resolver consumes only the assessment. It does NOT inspect
    readiness reports, transition explanations, or impact summaries,
    execute remediation, send notifications, access repositories, or
    read the clock.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same assessment always produces the same recommendation
    - Side-effect free: Never mutates the assessment, never acts
    """

    def resolve(
        self,
        assessment: (
            ResearchWorkspaceConsumerProjectionReadinessAssessmentReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessRecommendationReport:
        """
        Resolve a readiness operational assessment into a response recommendation.

        Args:
            assessment: The operational assessment to resolve

        Returns:
            An immutable, deterministic response recommendation
        """

        recommendation = _RECOMMENDATIONS[assessment.assessment]

        return ResearchWorkspaceConsumerProjectionReadinessRecommendationReport(
            projection_name=assessment.projection_name,
            assessment=assessment.assessment,
            recommendation=recommendation,
        )
