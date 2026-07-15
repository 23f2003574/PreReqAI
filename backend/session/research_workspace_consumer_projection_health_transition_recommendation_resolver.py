from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_assessment_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
)

from .research_workspace_consumer_projection_health_transition_recommendation import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation,
)

from .research_workspace_consumer_projection_health_transition_recommendation_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
)


# Direct, static mapping from operational assessment to recommended
# response posture - deliberately not a nested conditional.
_RECOMMENDATIONS = {
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.CONTINUE_OBSERVATION
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.RECOVERED: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.REVIEW_CHANGES
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.INVESTIGATE
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.PRIORITIZE_REVIEW
    ),
}


class ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver:
    """
    Resolves a Commit #7 operational assessment into a generic
    recommended response posture.

    The resolver consumes only the assessment. It does NOT inspect
    execution receipts, inspect quality signals, recalculate health,
    recalculate transitions, execute remediation, send notifications,
    access repositories, or read the clock.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same assessment always produces the same recommendation
    - Side-effect free: Never mutates the assessment, never acts
    """

    def resolve(
        self,
        assessment: (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessment
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation:
        """
        Resolve an operational assessment into a response recommendation.

        Args:
            assessment: The operational assessment to resolve

        Returns:
            An immutable, deterministic response recommendation
        """

        recommendation_kind = _RECOMMENDATIONS[assessment.assessment]

        return ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation(
            projection_name=assessment.projection_name,
            previous_execution_id=assessment.previous_execution_id,
            current_execution_id=assessment.current_execution_id,
            assessment=assessment.assessment,
            recommendation=recommendation_kind,
        )
