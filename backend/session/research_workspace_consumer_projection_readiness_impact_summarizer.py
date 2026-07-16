from .research_workspace_consumer_projection_readiness_impact import (
    ResearchWorkspaceConsumerProjectionReadinessImpact,
)

from .research_workspace_consumer_projection_readiness_impact_summary import (
    ResearchWorkspaceConsumerProjectionReadinessImpactSummary,
)

from .research_workspace_consumer_projection_readiness_transition_explanation import (
    ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation,
)


class ResearchWorkspaceConsumerProjectionReadinessImpactSummarizer:
    """
    Reduces a Commit #5 readiness transition explanation into a
    compact directional impact classification plus issue-level
    counts.

    The summarizer works entirely from the already-computed
    explanation. It does NOT inspect readiness reports, re-run
    readiness evaluation, recalculate the transition, rebuild the
    explanation, access repositories, or read the clock.

    The summarizer is:
    - Stateless: No instance state
    - Deterministic: Same explanation always produces the same summary
    - Side-effect free: Never mutates the explanation
    """

    def summarize(
        self,
        explanation: (
            ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessImpactSummary:
        """
        Summarize a readiness transition explanation into an impact summary.

        Args:
            explanation: The transition explanation to reduce

        Returns:
            An immutable, deterministic transition impact summary
        """

        appeared_count = len(explanation.appeared_issues)
        resolved_count = len(explanation.resolved_issues)
        persistent_count = len(explanation.persistent_issues)

        has_positive = resolved_count > 0
        has_negative = appeared_count > 0

        if has_positive and has_negative:
            impact = (
                ResearchWorkspaceConsumerProjectionReadinessImpact.MIXED
            )
        elif has_positive:
            impact = (
                ResearchWorkspaceConsumerProjectionReadinessImpact.POSITIVE
            )
        elif has_negative:
            impact = (
                ResearchWorkspaceConsumerProjectionReadinessImpact.NEGATIVE
            )
        else:
            impact = (
                ResearchWorkspaceConsumerProjectionReadinessImpact.NONE
            )

        return ResearchWorkspaceConsumerProjectionReadinessImpactSummary(
            projection_name=explanation.projection_name,
            transition=explanation.transition,
            impact=impact,
            appeared_count=appeared_count,
            resolved_count=resolved_count,
            persistent_count=persistent_count,
        )
