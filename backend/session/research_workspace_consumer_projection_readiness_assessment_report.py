from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_assessment import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
)

from .research_workspace_consumer_projection_readiness_impact import (
    ResearchWorkspaceConsumerProjectionReadinessImpact,
)

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessAssessmentReport:
    """
    Compact operational assessment combining an existing readiness
    transition (Commit #4) and transition impact summary (Commit #6)
    into one decision-ready classification.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        transition: Readiness transition reused from the input artifacts
        impact: Transition impact reused from the input artifacts
        assessment: The resolved operational assessment
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

    @property
    def requires_attention(self) -> bool:
        return self.assessment in {
            ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED,
            ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING,
            ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED,
        }

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "transition": self.transition.value,
            "impact": self.impact.value,
            "assessment": self.assessment.value,
            "requires_attention": self.requires_attention,
        }
