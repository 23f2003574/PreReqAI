from .research_workspace_consumer_projection_health_transition_explanation import (
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanation,
)

from .research_workspace_consumer_projection_health_transition_impact import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
)

from .research_workspace_consumer_projection_health_transition_impact_summary import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary,
)

from .research_workspace_consumer_projection_quality_signal_severity import (
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity,
)


# Ordering exists only to determine severity change direction -
# never exposed as a public numeric score.
_SEVERITY_ORDER = {
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity.INFO: 0,
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity.WARNING: 1,
    ResearchWorkspaceConsumerProjectionQualitySignalSeverity.CRITICAL: 2,
}


class ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummarizer:
    """
    Reduces a Commit #5 health transition explanation into a compact
    directional impact classification plus signal-level counts.

    The summarizer works entirely from the already-computed
    explanation. It does NOT inspect execution receipts, re-extract
    quality signals, recalculate health, recalculate the transition,
    rebuild the explanation, access repositories, or read the clock.

    The summarizer is:
    - Stateless: No instance state
    - Deterministic: Same explanation always produces the same summary
    - Side-effect free: Never mutates the explanation
    """

    def summarize(
        self,
        explanation: (
            ResearchWorkspaceConsumerProjectionHealthTransitionExplanation
        ),
    ) -> ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary:
        """
        Summarize a health transition explanation into an impact summary.

        Args:
            explanation: The transition explanation to reduce

        Returns:
            An immutable, deterministic transition impact summary
        """

        appeared_count = len(explanation.appeared_signals)
        resolved_count = len(explanation.resolved_signals)
        persistent_count = len(explanation.persistent_signals)

        severity_increase_count = 0
        severity_decrease_count = 0

        for change in explanation.severity_changes:
            previous_order = _SEVERITY_ORDER[change.previous_severity]
            current_order = _SEVERITY_ORDER[change.current_severity]

            if current_order > previous_order:
                severity_increase_count += 1
            elif current_order < previous_order:
                severity_decrease_count += 1

        has_positive = (
            resolved_count > 0 or severity_decrease_count > 0
        )
        has_negative = (
            appeared_count > 0 or severity_increase_count > 0
        )

        if has_positive and has_negative:
            impact = (
                ResearchWorkspaceConsumerProjectionHealthTransitionImpact.MIXED
            )
        elif has_positive:
            impact = (
                ResearchWorkspaceConsumerProjectionHealthTransitionImpact.POSITIVE
            )
        elif has_negative:
            impact = (
                ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NEGATIVE
            )
        else:
            impact = (
                ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NONE
            )

        return ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary(
            projection_name=explanation.projection_name,
            previous_execution_id=explanation.previous_execution_id,
            current_execution_id=explanation.current_execution_id,
            transition=explanation.transition,
            impact=impact,
            appeared_count=appeared_count,
            resolved_count=resolved_count,
            persistent_count=persistent_count,
            severity_increase_count=severity_increase_count,
            severity_decrease_count=severity_decrease_count,
        )
