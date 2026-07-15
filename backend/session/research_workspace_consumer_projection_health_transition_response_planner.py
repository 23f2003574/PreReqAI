from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_recommendation_resolver import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver,
)

from .research_workspace_consumer_projection_health_transition_response_directive import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective,
)

from .research_workspace_consumer_projection_health_transition_response_directive_builder import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder,
)

from .research_workspace_consumer_projection_health_transition_response_priority_resolver import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner:
    """
    Convenience composition of the recommendation resolver
    (Commit #8), the priority resolver (Commit #9), and the response
    directive builder (this commit), for callers that only have an
    operational assessment and want the resulting response directive
    directly.

    This is purely composition - it owns no recommendation-mapping,
    priority-mapping, or directive-building logic of its own. Each
    existing service keeps owning its own decision.
    """

    def __init__(
        self,
        recommendation_resolver: (
            ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver
        ) = None,
        priority_resolver: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver
        ) = None,
        directive_builder: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder
        ) = None,
    ):
        self._recommendation_resolver = (
            recommendation_resolver
            or ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        )

        self._priority_resolver = (
            priority_resolver
            or ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        )

        self._directive_builder = (
            directive_builder
            or ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        )

    def plan(
        self,
        assessment: (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessment
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective:
        """
        Resolve an operational assessment directly into a response directive.

        Args:
            assessment: The operational assessment to plan a response for

        Returns:
            An immutable response directive
        """

        recommendation = self._recommendation_resolver.resolve(assessment)
        priority = self._priority_resolver.resolve(recommendation)

        return self._directive_builder.build(recommendation, priority)
