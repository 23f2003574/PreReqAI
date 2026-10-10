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
class ResearchWorkspaceConsumerProjectionReadinessRationale:
    """
    Compact, deterministic reason for a Commit #10 readiness
    directive, derived from the Commit #7 operational assessment.

    The summary is fixed text per reason code - never dynamically
    generated prose, and never includes issue codes, projection
    names, or counts (those already exist as structured fields
    elsewhere in the pipeline).

    Attributes:
        projection_name: Projection name reused from the input artifacts
        reason: Compact reason code resolved from the assessment
        recommendation: Recommendation reused from the readiness directive
        priority: Priority reused from the readiness directive
        summary: Fixed, deterministic summary text for the reason
    """

    projection_name: str

    reason: (
        ResearchWorkspaceConsumerProjectionReadinessReasonCode
    )

    recommendation: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation
    )

    priority: (
        ResearchWorkspaceConsumerProjectionReadinessPriority
    )

    summary: str

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "reason": self.reason.value,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "summary": self.summary,
        }
