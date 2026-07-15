from .research_workspace_consumer_projection_execution_health_transition import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
)

from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_assessor import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessor,
)

from .research_workspace_consumer_projection_health_transition_explanation import (
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanation,
)

from .research_workspace_consumer_projection_health_transition_impact_summarizer import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer,
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

from .research_workspace_consumer_projection_health_transition_response_plan_snapshot import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshot,
)

from .research_workspace_consumer_projection_health_transition_response_plan_snapshot_builder import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder,
)

from .research_workspace_consumer_projection_health_transition_response_priority_resolver import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver,
)

from .research_workspace_consumer_projection_health_transition_response_rationale_builder import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner:
    """
    Convenience composition of the full response pipeline for callers
    that only have upstream artifacts and want a finalized result
    directly, without wiring each layer themselves.

    `plan(assessment)` delegates through the recommendation resolver
    (Commit #8), the priority resolver (Commit #9), the response
    directive builder (Commit #10), the response rationale builder
    (Commit #11), and the response package builder (Commit #12) to
    produce a response package.

    `build_snapshot(transition, explanation)` delegates further back,
    through the impact summarizer (Commit #6) and the assessor
    (Commit #7), then through the same response pipeline as `plan`,
    finally through the response plan snapshot builder (this commit)
    to produce a complete decision-chain snapshot.

    This is purely composition - it owns no impact-summarization,
    assessment, recommendation-mapping, priority-mapping,
    directive-building, rationale-building, package-building, or
    snapshot-building logic of its own. Each existing service keeps
    owning its own decision; the planner only delegates through them
    in order.
    """

    def __init__(
        self,
        impact_summarizer: (
            ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer
        ) = None,
        assessor: (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessor
        ) = None,
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
        snapshot_builder: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder
        ) = None,
    ):
        self._impact_summarizer = (
            impact_summarizer
            or ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer()
        )

        self._assessor = (
            assessor
            or ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        )

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

        self._snapshot_builder = (
            snapshot_builder
            or ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
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

    def build_snapshot(
        self,
        transition: (
            ResearchWorkspaceConsumerProjectionExecutionHealthTransition
        ),
        explanation: (
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanation
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshot:
        """
        Resolve a transition and its explanation directly into a
        complete response plan snapshot.

        Args:
            transition: The health transition to build a snapshot for
            explanation: The transition explanation describing the same pair

        Returns:
            An immutable response plan snapshot
        """

        impact = self._impact_summarizer.summarize(explanation)
        assessment = self._assessor.assess(transition, impact)
        response = self.plan(assessment)

        return self._snapshot_builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )
