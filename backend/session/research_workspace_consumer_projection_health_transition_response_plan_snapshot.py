from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_health_transition_assessment_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
)

from .research_workspace_consumer_projection_health_transition_impact import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
)

from .research_workspace_consumer_projection_health_transition_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
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
class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshot:
    """
    Compact, immutable representation of the complete finalized
    health-transition decision chain for one execution pair.

    Bundles the Commit #4 transition kind, Commit #6 impact, Commit
    #7 assessment, and Commit #12 response package into one flat
    object - the earlier artifacts remain useful for specialized
    consumers (detailed signal evidence, signal-level direction,
    operational interpretation), while this snapshot is the one
    compact handoff point for a future API, dashboard, logging, or
    persistence layer.

    Carries no mutable workflow state (acknowledged, assigned to,
    completed, dismissed, retry count, current status) - those
    belong to a future workflow system, not this decision engine.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        previous_execution_id: Execution ID reused from the input artifacts
        current_execution_id: Execution ID reused from the input artifacts
        transition: Transition kind reused from the health transition
        impact: Impact reused from the impact summary
        assessment: Assessment kind reused from the assessment
        recommendation: Recommendation reused from the response package
        priority: Priority reused from the response package
        reason: Reason code reused from the response package
        summary: Summary text reused from the response package
        action_recommended: Action flag reused from the response package
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    transition: (
        ResearchWorkspaceConsumerProjectionHealthTransitionKind
    )

    impact: (
        ResearchWorkspaceConsumerProjectionHealthTransitionImpact
    )

    assessment: (
        ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind
    )

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
        Serialize the response plan snapshot to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "transition": self.transition.value,
            "impact": self.impact.value,
            "assessment": self.assessment.value,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "reason": self.reason.value,
            "summary": self.summary,
            "action_recommended": self.action_recommended,
        }
