from .research_workspace_consumer_projection_health_transition_recommendation import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation,
)

from .research_workspace_consumer_projection_health_transition_response_directive import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective,
)

from .research_workspace_consumer_projection_health_transition_response_directive_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError,
)

from .research_workspace_consumer_projection_health_transition_response_priority_result import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder:
    """
    Combines an existing response recommendation (Commit #8) and
    response priority result (Commit #9) into one immutable response
    directive.

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
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation
        ),
        priority: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective:
        """
        Build a response directive from a recommendation and priority result.

        Args:
            recommendation: The response recommendation to combine
            priority: The response priority result describing the same pair

        Returns:
            An immutable response directive

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError:
                If the two artifacts do not describe the same execution
                pair, projection, or recommendation kind
        """

        self._validate_alignment(
            recommendation=recommendation,
            priority=priority,
        )

        return ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective(
            projection_name=recommendation.projection_name,
            previous_execution_id=recommendation.previous_execution_id,
            current_execution_id=recommendation.current_execution_id,
            recommendation=recommendation.recommendation,
            priority=priority.priority,
        )

    def _validate_alignment(self, *, recommendation, priority):
        if recommendation.projection_name != priority.projection_name:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError(
                "Cannot build a response directive from a recommendation "
                f"and priority describing different projections: "
                f"'{recommendation.projection_name}' vs "
                f"'{priority.projection_name}'"
            )

        if recommendation.previous_execution_id != priority.previous_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError(
                "Recommendation previous execution ID "
                f"'{recommendation.previous_execution_id}' does not match "
                f"priority result previous execution ID "
                f"'{priority.previous_execution_id}'"
            )

        if recommendation.current_execution_id != priority.current_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError(
                "Recommendation current execution ID "
                f"'{recommendation.current_execution_id}' does not match "
                f"priority result current execution ID "
                f"'{priority.current_execution_id}'"
            )

        if recommendation.recommendation != priority.recommendation:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError(
                f"Recommendation kind '{recommendation.recommendation.value}' "
                f"does not match priority result recommendation kind "
                f"'{priority.recommendation.value}'"
            )
