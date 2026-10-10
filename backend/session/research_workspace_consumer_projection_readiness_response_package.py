from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_priority import (
    ResearchWorkspaceConsumerProjectionReadinessPriority,
)

from .research_workspace_consumer_projection_readiness_reason_code import (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode,
)

from .research_workspace_consumer_projection_readiness_recommendation import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessResponsePackage:
    """
    Portable, immutable, consumer-facing bundle of the finalized
    readiness response for one projection.

    Combines a Commit #10 readiness directive (what to do, how
    urgently) and a Commit #11 readiness rationale (why) into one
    flat result that a future API, logging adapter, or dashboard can
    consume without traversing readiness reports, transition
    explanations, impact summaries, or assessments.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        recommendation: Recommendation reused from the readiness directive
        priority: Priority reused from the readiness directive
        reason: Reason code reused from the readiness rationale
        summary: Summary text reused from the readiness rationale
        action_required: Action flag reused from the readiness directive
    """

    projection_name: str

    recommendation: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation
    )

    priority: (
        ResearchWorkspaceConsumerProjectionReadinessPriority
    )

    reason: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode
    )

    summary: str

    action_required: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "reason": self.reason.value,
            "summary": self.summary,
            "action_required": self.action_required,
        }
