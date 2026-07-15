from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_recommendation_resolver import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver,
)

from .research_workspace_consumer_projection_health_transition_response_directive_builder import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder,
)

from .research_workspace_consumer_projection_health_transition_response_package import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage,
)

from .research_workspace_consumer_projection_health_transition_response_package_builder import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder,
)

from .research_workspace_consumer_projection_health_transition_response_priority_resolver import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver,
)

from .research_workspace_consumer_projection_health_transition_response_rationale_builder import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner:
    """
    Convenience composition of the full response pipeline - the
    recommendation resolver (Commit #8), the priority resolver
    (Commit #9), the response directive builder (Commit #10), the
    response rationale builder (Commit #11), and the response
    package builder (this commit) - for callers that only have an
    operational assessment and want the finalized response package
    directly.

    This is purely composition - it owns no recommendation-mapping,
    priority-mapping, directive-building, rationale-building, or
    package-building logic of its own. Each existing service keeps
    owning its own decision; the planner only delegates through them
    in order.
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
        rationale_builder: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder
        ) = None,
        package_builder: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder
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

        self._rationale_builder = (
            rationale_builder
            or ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        )

        self._package_builder = (
            package_builder
            or ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        )

    def plan(
        self,
        assessment: (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessment
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage:
        """
        Resolve an operational assessment directly into a response package.

        Args:
            assessment: The operational assessment to plan a response for

        Returns:
            An immutable, portable response package
        """

        recommendation = self._recommendation_resolver.resolve(assessment)
        priority = self._priority_resolver.resolve(recommendation)
        directive = self._directive_builder.build(recommendation, priority)
        rationale = self._rationale_builder.build(assessment, directive)

        return self._package_builder.build(directive, rationale)
