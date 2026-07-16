from .research_workspace_consumer_projection_readiness_assessment import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
)

from .research_workspace_consumer_projection_readiness_assessment_report import (
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
)

from .research_workspace_consumer_projection_readiness_directive import (
    ResearchWorkspaceConsumerProjectionReadinessDirective,
)

from .research_workspace_consumer_projection_readiness_rationale import (
    ResearchWorkspaceConsumerProjectionReadinessRationale,
)

from .research_workspace_consumer_projection_readiness_reason_code import (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode,
)


# Direct mapping from operational assessment to reason code.
_REASON_BY_ASSESSMENT = {
    ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode.READY
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode.IMPROVING
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode.RECOVERED
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode.MIXED
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode.DETERIORATING
    ),
    ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode.BLOCKED
    ),
}

# Fixed, deterministic summary text per reason code.
_SUMMARY_BY_REASON = {
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.READY: (
        "Projection is ready."
    ),
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.IMPROVING: (
        "Projection readiness is improving."
    ),
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.RECOVERED: (
        "Projection readiness recovered."
    ),
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.MIXED: (
        "Projection readiness changed."
    ),
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.DETERIORATING: (
        "Projection readiness is deteriorating."
    ),
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.BLOCKED: (
        "Projection execution is blocked."
    ),
}


class ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder:
    """
    Combines an existing operational assessment (Commit #7) and
    readiness directive (Commit #10) into one immutable readiness
    rationale: a compact reason code and stable summary text.

    The builder combines already-finalized artifacts only. It does
    NOT inspect readiness reports, rebuild transition explanations,
    recalculate recommendations, recalculate priorities, call an
    LLM, access repositories, or read the clock. The reason code is
    resolved purely from the assessment, reusing a static mapping
    rather than re-deriving it from the directive.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same rationale
    - Side-effect free: Never mutates either input artifact
    """

    def build(
        self,
        assessment: (
            ResearchWorkspaceConsumerProjectionReadinessAssessmentReport
        ),
        directive: (
            ResearchWorkspaceConsumerProjectionReadinessDirective
        ),
    ) -> ResearchWorkspaceConsumerProjectionReadinessRationale:
        """
        Build a readiness rationale from an assessment and a readiness directive.

        Args:
            assessment: The operational assessment to explain
            directive: The readiness directive to attach reason text to

        Returns:
            An immutable readiness rationale
        """

        reason = _REASON_BY_ASSESSMENT[assessment.assessment]
        summary = _SUMMARY_BY_REASON[reason]

        return ResearchWorkspaceConsumerProjectionReadinessRationale(
            projection_name=assessment.projection_name,
            reason=reason,
            recommendation=directive.recommendation,
            priority=directive.priority,
            summary=summary,
        )
