from .research_workspace_consumer_projection_readiness_assessment_report import (
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
)

from .research_workspace_consumer_projection_readiness_decision_snapshot import (
    ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshot,
)

from .research_workspace_consumer_projection_readiness_decision_snapshot_error import (
    ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError,
)

from .research_workspace_consumer_projection_readiness_impact_summary import (
    ResearchWorkspaceConsumerProjectionReadinessImpactSummary,
)

from .research_workspace_consumer_projection_readiness_response_package import (
    ResearchWorkspaceConsumerProjectionReadinessResponsePackage,
)

from .research_workspace_consumer_projection_readiness_transition_report import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


class ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder:
    """
    Validates and composes an existing readiness transition
    (Commit #4), impact summary (Commit #6), assessment (Commit #7),
    and response package (Commit #12) into one immutable readiness
    decision snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run readiness evaluation,
    rebuild the transition explanation, recalculate the
    recommendation, priority, or reason, access repositories, or
    read the clock.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same snapshot
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        transition: (
            ResearchWorkspaceConsumerProjectionReadinessTransitionReport
        ),
        impact: (
            ResearchWorkspaceConsumerProjectionReadinessImpactSummary
        ),
        assessment: (
            ResearchWorkspaceConsumerProjectionReadinessAssessmentReport
        ),
        response: (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackage
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshot:
        """
        Build a decision snapshot from the finalized readiness decision chain.

        Args:
            transition: The readiness transition for this projection
            impact: The impact summary describing the same transition
            assessment: The assessment describing the same transition/impact
            response: The response package describing the same assessment

        Returns:
            An immutable readiness decision snapshot

        Raises:
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError:
                If the artifacts do not describe the same projection,
                or the impact/assessment disagree on the transition
                they share
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
        )

        return ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshot(
            projection_name=transition.projection_name,
            transition=transition.transition,
            impact=impact.impact,
            assessment=assessment.assessment,
            recommendation=response.recommendation,
            priority=response.priority,
            reason=response.reason,
            summary=response.summary,
            action_required=response.action_required,
        )

    def _validate_identity(self, *, transition, impact, assessment, response):
        for name, artifact in (
            ("impact summary", impact),
            ("assessment", assessment),
            ("response package", response),
        ):
            if artifact.projection_name != transition.projection_name:
                raise ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError(
                    f"Cannot build a decision snapshot: {name} "
                    f"projection name '{artifact.projection_name}' does "
                    f"not match transition projection name "
                    f"'{transition.projection_name}'"
                )

    def _validate_continuity(self, *, transition, impact, assessment):
        if impact.transition != transition.transition:
            raise ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError(
                f"Impact summary transition "
                f"'{impact.transition.value}' does not match transition "
                f"'{transition.transition.value}'"
            )

        if assessment.transition != transition.transition:
            raise ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError(
                f"Assessment transition '{assessment.transition.value}' "
                f"does not match transition '{transition.transition.value}'"
            )

        if assessment.impact != impact.impact:
            raise ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError(
                f"Assessment impact '{assessment.impact.value}' does not "
                f"match impact summary impact '{impact.impact.value}'"
            )
