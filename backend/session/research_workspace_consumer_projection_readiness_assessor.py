from .research_workspace_consumer_projection_readiness_assessment import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
)

from .research_workspace_consumer_projection_readiness_assessment_error import (
    ResearchWorkspaceConsumerProjectionReadinessAssessmentError,
)

from .research_workspace_consumer_projection_readiness_assessment_report import (
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
)

from .research_workspace_consumer_projection_readiness_impact import (
    ResearchWorkspaceConsumerProjectionReadinessImpact,
)

from .research_workspace_consumer_projection_readiness_impact_summary import (
    ResearchWorkspaceConsumerProjectionReadinessImpactSummary,
)

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)

from .research_workspace_consumer_projection_readiness_transition_report import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


class ResearchWorkspaceConsumerProjectionReadinessAssessor:
    """
    Combines an existing readiness transition (Commit #4) and
    transition impact summary (Commit #6) into one compact
    operational assessment.

    The assessor combines already-finalized artifacts only. It does
    NOT inspect readiness reports, re-run readiness evaluation,
    rebuild the transition explanation, recalculate impact, access
    repositories, or read the clock.

    The assessor is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same assessment
    - Side-effect free: Never mutates either input artifact
    """

    def assess(
        self,
        transition: (
            ResearchWorkspaceConsumerProjectionReadinessTransitionReport
        ),
        impact: (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummary
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessAssessmentReport:
        """
        Assess a readiness transition together with its impact summary.

        Args:
            transition: The readiness transition to assess
            impact: The transition impact summary describing the same transition

        Returns:
            An immutable operational assessment

        Raises:
            ResearchWorkspaceConsumerProjectionReadinessAssessmentError:
                If the two artifacts do not describe the same
                projection or transition
        """

        self._validate_alignment(transition=transition, impact=impact)

        assessment = self._resolve_assessment(
            transition_kind=transition.transition,
            impact_kind=impact.impact,
        )

        return ResearchWorkspaceConsumerProjectionReadinessAssessmentReport(
            projection_name=transition.projection_name,
            transition=transition.transition,
            impact=impact.impact,
            assessment=assessment,
        )

    def _validate_alignment(self, *, transition, impact):
        if transition.projection_name != impact.projection_name:
            raise ResearchWorkspaceConsumerProjectionReadinessAssessmentError(
                "Cannot assess a transition and impact summary "
                f"describing different projections: "
                f"'{transition.projection_name}' vs "
                f"'{impact.projection_name}'"
            )

        if transition.transition != impact.transition:
            raise ResearchWorkspaceConsumerProjectionReadinessAssessmentError(
                f"Transition '{transition.transition.value}' does not "
                f"match impact summary transition "
                f"'{impact.transition.value}'"
            )

    def _resolve_assessment(
        self,
        *,
        transition_kind: (
            ResearchWorkspaceConsumerProjectionReadinessTransition
        ),
        impact_kind: (
            ResearchWorkspaceConsumerProjectionReadinessImpact
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessAssessment:
        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED
            )

        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED
            )

        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionReadinessTransition.IMPROVED
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING
            )

        if (
            transition_kind
            == ResearchWorkspaceConsumerProjectionReadinessTransition.DEGRADED
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING
            )

        # transition_kind == UNCHANGED: fall through to issue-level impact.
        if (
            impact_kind
            == ResearchWorkspaceConsumerProjectionReadinessImpact.MIXED
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED
            )

        if (
            impact_kind
            == ResearchWorkspaceConsumerProjectionReadinessImpact.NEGATIVE
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING
            )

        if (
            impact_kind
            == ResearchWorkspaceConsumerProjectionReadinessImpact.POSITIVE
        ):
            return (
                ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING
            )

        # impact_kind == NONE
        return (
            ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE
        )
