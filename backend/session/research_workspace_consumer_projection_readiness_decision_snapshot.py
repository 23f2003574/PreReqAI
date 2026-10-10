from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_assessment import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
)

from .research_workspace_consumer_projection_readiness_impact import (
    ResearchWorkspaceConsumerProjectionReadinessImpact,
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

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshot:
    """
    Compact, immutable representation of the complete finalized
    readiness decision chain for one projection.

    Bundles the Commit #4 transition, Commit #6 impact, Commit #7
    assessment, and Commit #12 response package into one flat object
    - the earlier artifacts remain useful for specialized consumers
    (issue-level explanations, transition analysis, operational
    interpretation), while this snapshot is the one compact handoff
    point for a future API, dashboard, logging, or persistence layer.

    Carries no mutable workflow state (acknowledged, assigned to,
    completed, dismissed, retry count, current status) - those
    belong to a future workflow system, not this decision engine.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        transition: Transition reused from the readiness transition
        impact: Impact reused from the impact summary
        assessment: Assessment reused from the assessment
        recommendation: Recommendation reused from the response package
        priority: Priority reused from the response package
        reason: Reason code reused from the response package
        summary: Summary text reused from the response package
        action_required: Action flag reused from the response package
    """

    projection_name: str

    transition: (
        ResearchWorkspaceConsumerProjectionReadinessTransition
    )

    impact: (
        ResearchWorkspaceConsumerProjectionReadinessImpact
    )

    assessment: (
        ResearchWorkspaceConsumerProjectionReadinessAssessment
    )

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
            "transition": self.transition.value,
            "impact": self.impact.value,
            "assessment": self.assessment.value,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "reason": self.reason.value,
            "summary": self.summary,
            "action_required": self.action_required,
        }
