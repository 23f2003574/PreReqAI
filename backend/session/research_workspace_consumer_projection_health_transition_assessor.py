from .research_workspace_consumer_projection_execution_health_transition import (
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
)

from .research_workspace_consumer_projection_health_transition_assessment import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
)

from .research_workspace_consumer_projection_health_transition_assessment_error import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError,
)

from .research_workspace_consumer_projection_health_transition_assessment_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
)

from .research_workspace_consumer_projection_health_transition_impact import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
)

from .research_workspace_consumer_projection_health_transition_impact_summary import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary,
)

from .research_workspace_consumer_projection_health_transition_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionAssessor:
    """
    Combines an existing health transition (Commit #4) and transition
    impact summary (Commit #6) into one compact operational
    assessment.

    The assessor combines already-finalized artifacts only. It does
    NOT inspect execution receipts, inspect quality signals, rebuild
    health summaries, recalculate transition explanations, access
    repositories, or read the clock.

    The assessor is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same assessment
    - Side-effect free: Never mutates either input artifact
    """

    def assess(
        self,
        transition: (
            ResearchWorkspaceConsumerProjectionExecutionHealthTransition
        ),
        impact: (
            ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionAssessment:
        """
        Assess a health transition together with its impact summary.

        Args:
            transition: The health transition to assess
            impact: The transition impact summary describing the same pair

        Returns:
            An immutable operational assessment

        Raises:
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError:
                If the two artifacts do not describe the same execution
                pair, projection, or transition kind
        """

        self._validate_alignment(transition=transition, impact=impact)

        assessment_kind = self._resolve_assessment(
            transition_kind=transition.kind,
            impact_kind=impact.impact,
        )

        return ResearchWorkspaceConsumerProjectionHealthTransitionAssessment(
            projection_name=transition.projection_name,
            previous_execution_id=transition.previous_execution_id,
            current_execution_id=transition.current_execution_id,
            transition=transition.kind,
            impact=impact.impact,
            assessment=assessment_kind,
        )

    def _validate_alignment(self, *, transition, impact):
        if transition.projection_name != impact.projection_name:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError(
                "Cannot assess a transition and impact summary "
                f"describing different projections: "
                f"'{transition.projection_name}' vs "
                f"'{impact.projection_name}'"
            )

        if transition.previous_execution_id != impact.previous_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError(
                "Transition previous execution ID "
                f"'{transition.previous_execution_id}' does not match "
                f"impact summary previous execution ID "
                f"'{impact.previous_execution_id}'"
            )

        if transition.current_execution_id != impact.current_execution_id:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError(
                "Transition current execution ID "
                f"'{transition.current_execution_id}' does not match "
                f"impact summary current execution ID "
                f"'{impact.current_execution_id}'"
            )

        if transition.kind != impact.transition:
            raise ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError(
                f"Transition kind '{transition.kind.value}' does not "
                f"match impact summary transition kind "
                f"'{impact.transition.value}'"
            )

    def _resolve_assessment(
        self,
        *,
        transition_kind: (
            ResearchWorkspaceConsumerProjectionHealthTransitionKind
        ),
        impact_kind: (
            ResearchWorkspaceConsumerProjectionHealthTransitionImpact
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind:
        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
            )

        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionKind.RECOVERED
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.RECOVERED
            )

        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionKind.IMPROVED
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING
            )

        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionKind.DETERIORATED
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING
            )

        # transition_kind == UNCHANGED: fall through to signal-level impact.
        if (
            impact_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionImpact.MIXED
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED
            )

        if (
            impact_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NEGATIVE
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING
            )

        if (
            impact_kind
            == ResearchWorkspaceConsumerProjectionHealthTransitionImpact.POSITIVE
        ):
            return (
                ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING
            )

        # impact_kind == NONE
        return (
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE
        )
