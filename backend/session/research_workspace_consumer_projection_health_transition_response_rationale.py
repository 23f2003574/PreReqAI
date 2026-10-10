from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_health_transition_recommendation_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
)

from .research_workspace_consumer_projection_health_transition_response_priority import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
)

from .research_workspace_consumer_projection_health_transition_response_reason import (
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale:
    """
    Compact, deterministic reason for a Commit #10 response
    directive, derived from the Commit #7 operational assessment.

    The summary is fixed text per reason code - never dynamically
    generated prose, and never includes execution IDs, projection
    names, timestamps, or signal counts (those already exist as
    structured fields elsewhere in the pipeline).

    Attributes:
        projection_name: Projection name reused from the input artifacts
        previous_execution_id: Execution ID reused from the input artifacts
        current_execution_id: Execution ID reused from the input artifacts
        reason: Compact reason code resolved from the assessment
        recommendation: Recommendation reused from the response directive
        priority: Priority reused from the response directive
        summary: Fixed, deterministic summary text for the reason
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    reason: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason
    )

    recommendation: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind
    )

    priority: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority
    )

    summary: str

    def to_dict(self):
        """
        Serialize the response rationale to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "reason": self.reason.value,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "summary": self.summary,
        }
