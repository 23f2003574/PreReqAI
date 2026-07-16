from .research_workspace_consumer_projection_readiness_directive import (
    ResearchWorkspaceConsumerProjectionReadinessDirective,
)

from .research_workspace_consumer_projection_readiness_directive_error import (
    ResearchWorkspaceConsumerProjectionReadinessDirectiveError,
)

from .research_workspace_consumer_projection_readiness_priority_report import (
    ResearchWorkspaceConsumerProjectionReadinessPriorityReport,
)

from .research_workspace_consumer_projection_readiness_recommendation_report import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendationReport,
)


class ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder:
    """
    Combines an existing readiness recommendation (Commit #8) and
    readiness priority report (Commit #9) into one immutable
    readiness directive.

    The builder validates and combines already-resolved artifacts
    only. It does NOT independently resolve the recommendation or
    priority again - those decisions belong to Commit #8 and Commit
    #9 respectively.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same directive
    - Side-effect free: Never mutates either input artifact
    """

    def build(
        self,
        recommendation: (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationReport
        ),
        priority: (
            ResearchWorkspaceConsumerProjectionReadinessPriorityReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessDirective:
        """
        Build a readiness directive from a recommendation and priority report.

        Args:
            recommendation: The readiness recommendation to combine
            priority: The readiness priority report describing the same recommendation

        Returns:
            An immutable readiness directive

        Raises:
            ResearchWorkspaceConsumerProjectionReadinessDirectiveError:
                If the two artifacts do not describe the same
                projection or recommendation
        """

        self._validate_alignment(
            recommendation=recommendation,
            priority=priority,
        )

        return ResearchWorkspaceConsumerProjectionReadinessDirective(
            projection_name=recommendation.projection_name,
            recommendation=recommendation.recommendation,
            priority=priority.priority,
        )

    def _validate_alignment(self, *, recommendation, priority):
        if recommendation.projection_name != priority.projection_name:
            raise ResearchWorkspaceConsumerProjectionReadinessDirectiveError(
                "Cannot build a readiness directive from a recommendation "
                f"and priority describing different projections: "
                f"'{recommendation.projection_name}' vs "
                f"'{priority.projection_name}'"
            )

        if recommendation.recommendation != priority.recommendation:
            raise ResearchWorkspaceConsumerProjectionReadinessDirectiveError(
                f"Recommendation '{recommendation.recommendation.value}' "
                f"does not match priority report recommendation "
                f"'{priority.recommendation.value}'"
            )
