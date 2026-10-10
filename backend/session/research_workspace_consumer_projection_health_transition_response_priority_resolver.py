from .research_workspace_consumer_projection_health_transition_recommendation import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation,
)

from .research_workspace_consumer_projection_health_transition_recommendation_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
)

from .research_workspace_consumer_projection_health_transition_response_priority import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
)

from .research_workspace_consumer_projection_health_transition_response_priority_result import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult,
)


# Direct, static mapping from response recommendation to relative
# response priority - deliberately not a nested conditional.
_PRIORITY_BY_RECOMMENDATION = {
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.CONTINUE_OBSERVATION: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.LOW
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.REVIEW_CHANGES: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.MEDIUM
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.INVESTIGATE: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.HIGH
    ),
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.PRIORITIZE_REVIEW: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.URGENT
    ),
}


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver:
    """
    Resolves a Commit #8 response recommendation into a relative
    response priority.

    The resolver consumes only the recommendation. It does NOT
    inspect execution receipts, inspect quality signals, recalculate
    assessments, execute recommendations, create tasks, send
    notifications, access repositories, or read the clock.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same recommendation always produces the same priority
    - Side-effect free: Never mutates the recommendation, never acts
    """

    def resolve(
        self,
        recommendation: (
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult:
        """
        Resolve a response recommendation into a relative response priority.

        Args:
            recommendation: The response recommendation to resolve

        Returns:
            An immutable, deterministic response priority result
        """

        priority = _PRIORITY_BY_RECOMMENDATION[
            recommendation.recommendation
        ]

        return ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult(
            projection_name=recommendation.projection_name,
            previous_execution_id=recommendation.previous_execution_id,
            current_execution_id=recommendation.current_execution_id,
            recommendation=recommendation.recommendation,
            priority=priority,
        )
