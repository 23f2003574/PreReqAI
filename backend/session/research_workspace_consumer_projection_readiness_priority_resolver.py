from .research_workspace_consumer_projection_readiness_priority import (
    ResearchWorkspaceConsumerProjectionReadinessPriority,
)

from .research_workspace_consumer_projection_readiness_priority_report import (
    ResearchWorkspaceConsumerProjectionReadinessPriorityReport,
)

from .research_workspace_consumer_projection_readiness_recommendation import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
)

from .research_workspace_consumer_projection_readiness_recommendation_report import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendationReport,
)


# Direct, static mapping from response recommendation to relative
# response priority - deliberately not a nested conditional.
_PRIORITY_BY_RECOMMENDATION = {
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION: (
        ResearchWorkspaceConsumerProjectionReadinessPriority.NONE
    ),
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.CONTINUE_MONITORING: (
        ResearchWorkspaceConsumerProjectionReadinessPriority.LOW
    ),
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.REVIEW_CHANGES: (
        ResearchWorkspaceConsumerProjectionReadinessPriority.MEDIUM
    ),
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.INVESTIGATE: (
        ResearchWorkspaceConsumerProjectionReadinessPriority.HIGH
    ),
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION: (
        ResearchWorkspaceConsumerProjectionReadinessPriority.CRITICAL
    ),
}


class ResearchWorkspaceConsumerProjectionReadinessPriorityResolver:
    """
    Resolves a Commit #8 readiness recommendation into a relative
    response priority.

    The resolver consumes only the recommendation. It does NOT
    inspect readiness reports, transition explanations, impact
    summaries, or assessments, execute recommendations, create
    tasks, send notifications, access repositories, or read the
    clock.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same recommendation always produces the same priority
    - Side-effect free: Never mutates the recommendation, never acts
    """

    def resolve(
        self,
        recommendation: (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessPriorityReport:
        """
        Resolve a readiness recommendation into a relative response priority.

        Args:
            recommendation: The readiness recommendation to resolve

        Returns:
            An immutable, deterministic response priority report
        """

        priority = _PRIORITY_BY_RECOMMENDATION[
            recommendation.recommendation
        ]

        return ResearchWorkspaceConsumerProjectionReadinessPriorityReport(
            projection_name=recommendation.projection_name,
            recommendation=recommendation.recommendation,
            priority=priority,
        )
