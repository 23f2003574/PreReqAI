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


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionHealthTransitionAssessment:
    """
    Compact operational assessment combining an existing health
    transition (Commit #4) and transition impact summary (Commit #6)
    into one decision-ready classification.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        previous_execution_id: Execution ID reused from the input artifacts
        current_execution_id: Execution ID reused from the input artifacts
        transition: Health transition kind reused from the input artifacts
        impact: Transition impact reused from the input artifacts
        assessment: The resolved operational assessment
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

    @property
    def requires_attention(self) -> bool:
        return self.assessment in {
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING,
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED,
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED,
        }

    def to_dict(self):
        """
        Serialize the assessment to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "transition": self.transition.value,
            "impact": self.impact.value,
            "assessment": self.assessment.value,
            "requires_attention": self.requires_attention,
        }
