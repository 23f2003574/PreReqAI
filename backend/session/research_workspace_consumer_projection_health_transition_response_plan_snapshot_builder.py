from .research_workspace_consumer_projection_execution_health_transition import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
)

from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_impact_summary import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary,
)

from .research_workspace_consumer_projection_health_transition_recommendation_resolver import (
    _RECOMMENDATIONS,
)

from .research_workspace_consumer_projection_health_transition_response_package import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage,
)

from .research_workspace_consumer_projection_health_transition_response_plan_snapshot import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshot,
)

from .research_workspace_consumer_projection_health_transition_response_plan_snapshot_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError,
)

from .research_workspace_consumer_projection_health_transition_response_priority_resolver import (
    _PRIORITY_BY_RECOMMENDATION,
)

from .research_workspace_consumer_projection_health_transition_response_rationale_builder import (
    _REASON_BY_ASSESSMENT,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder:
    """
    Validates and composes an existing health transition (Commit #4),
    impact summary (Commit #6), assessment (Commit #7), and response
    package (Commit #12) into one immutable response plan snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. Decision-continuity checks reuse the
    exact mapping tables Commit #8, Commit #9, and Commit #11 already
    define (`_RECOMMENDATIONS`, `_PRIORITY_BY_RECOMMENDATION`,
    `_REASON_BY_ASSESSMENT`) rather than inventing new compatibility
    rules or invoking those resolvers/builders again.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same snapshot
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        transition: (
            ResearchWorkspaceConsumerProjectionExecutionHealthTransition
        ),
        impact: (
            ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary
        ),
        assessment: (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessment
        ),
        response: (
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshot:
        """
        Build a response plan snapshot from the finalized decision chain.

        Args:
            transition: The health transition for this execution pair
            impact: The impact summary describing the same transition
            assessment: The assessment describing the same transition/impact
            response: The response package describing the same assessment

        Returns:
            An immutable response plan snapshot

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError:
                If the artifacts do not describe the same execution pair
                and projection, or disagree on the decisions they share
        """

        self._validate_identity(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        self._validate_continuity(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        return ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshot(
            projection_name=transition.projection_name,
            previous_execution_id=transition.previous_execution_id,
            current_execution_id=transition.current_execution_id,
            transition=transition.kind,
            impact=impact.impact,
            assessment=assessment.assessment,
            recommendation=response.recommendation,
            priority=response.priority,
            reason=response.reason,
            summary=response.summary,
            action_recommended=response.action_recommended,
        )

    def _validate_identity(self, *, transition, impact, assessment, response):
        for name, artifact in (
            ("impact summary", impact),
            ("assessment", assessment),
            ("response package", response),
        ):
            if artifact.projection_name != transition.projection_name:
                raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                    f"Cannot build a response plan snapshot: {name} "
                    f"projection name '{artifact.projection_name}' does "
                    f"not match transition projection name "
                    f"'{transition.projection_name}'"
                )

            if artifact.previous_execution_id != transition.previous_execution_id:
                raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                    f"Cannot build a response plan snapshot: {name} "
                    f"previous execution ID "
                    f"'{artifact.previous_execution_id}' does not match "
                    f"transition previous execution ID "
                    f"'{transition.previous_execution_id}'"
                )

            if artifact.current_execution_id != transition.current_execution_id:
                raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                    f"Cannot build a response plan snapshot: {name} "
                    f"current execution ID "
                    f"'{artifact.current_execution_id}' does not match "
                    f"transition current execution ID "
                    f"'{transition.current_execution_id}'"
                )

    def _validate_continuity(self, *, transition, impact, assessment, response):
        if impact.transition != transition.kind:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                f"Impact summary transition kind "
                f"'{impact.transition.value}' does not match transition "
                f"kind '{transition.kind.value}'"
            )

        if assessment.transition != transition.kind:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                f"Assessment transition kind '{assessment.transition.value}' "
                f"does not match transition kind '{transition.kind.value}'"
            )

        if assessment.impact != impact.impact:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                f"Assessment impact '{assessment.impact.value}' does not "
                f"match impact summary impact '{impact.impact.value}'"
            )

        expected_recommendation = _RECOMMENDATIONS[assessment.assessment]
        if response.recommendation != expected_recommendation:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                f"Response package recommendation "
                f"'{response.recommendation.value}' is not compatible "
                f"with assessment '{assessment.assessment.value}' "
                f"(expected '{expected_recommendation.value}')"
            )

        expected_priority = _PRIORITY_BY_RECOMMENDATION[
            response.recommendation
        ]
        if response.priority != expected_priority:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                f"Response package priority '{response.priority.value}' "
                f"is not compatible with recommendation "
                f"'{response.recommendation.value}' (expected "
                f"'{expected_priority.value}')"
            )

        expected_reason = _REASON_BY_ASSESSMENT[assessment.assessment]
        if response.reason != expected_reason:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
                f"Response package reason '{response.reason.value}' is "
                f"not compatible with assessment "
                f"'{assessment.assessment.value}' (expected "
                f"'{expected_reason.value}')"
            )
