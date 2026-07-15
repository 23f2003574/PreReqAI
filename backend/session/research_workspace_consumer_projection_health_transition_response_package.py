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
class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage:
    """
    Portable, immutable, consumer-facing bundle of the finalized
    response decision for one execution-health transition.

    Combines a Commit #10 response directive (what to do, how
    urgently) and a Commit #11 response rationale (why) into one flat
    result that a future API, logging adapter, or dashboard can
    consume without traversing execution receipts, quality signal
    reports, health summaries, transition explanations, or impact
    summaries.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        previous_execution_id: Execution ID reused from the input artifacts
        current_execution_id: Execution ID reused from the input artifacts
        recommendation: Recommendation reused from the response directive
        priority: Priority reused from the response directive
        reason: Reason code reused from the response rationale
        summary: Summary text reused from the response rationale
        action_recommended: Action flag reused from the response directive
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    recommendation: (
        ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind
    )

    priority: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority
    )

    reason: (
        ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason
    )

    summary: str

    action_recommended: bool

    def to_dict(self):
        """
        Serialize the response package to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "reason": self.reason.value,
            "summary": self.summary,
            "action_recommended": self.action_recommended,
        }
