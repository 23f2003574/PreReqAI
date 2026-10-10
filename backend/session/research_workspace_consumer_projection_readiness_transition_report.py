from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness import (
    ResearchWorkspaceConsumerProjectionReadiness,
)

from .research_workspace_consumer_projection_readiness_reason import (
    ResearchWorkspaceConsumerProjectionReadinessReason,
)

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessTransitionReport:
    """
    Result of comparing two consumer projection readiness reports.

    Describes the direction of readiness movement between a
    previous and a current evaluation of the same projection, while
    preserving both evaluations' primary reasons.

    Attributes:
        projection_name: Name of the compared projection
        previous_readiness: Readiness classification of the earlier report
        current_readiness: Readiness classification of the later report
        transition: Directional classification of the readiness movement
        previous_reason: Primary reason of the earlier report
        current_reason: Primary reason of the later report
    """

    projection_name: str

    previous_readiness: (
        ResearchWorkspaceConsumerProjectionReadiness
    )

    current_readiness: (
        ResearchWorkspaceConsumerProjectionReadiness
    )

    transition: (
        ResearchWorkspaceConsumerProjectionReadinessTransition
    )

    previous_reason: (
        ResearchWorkspaceConsumerProjectionReadinessReason
    )

    current_reason: (
        ResearchWorkspaceConsumerProjectionReadinessReason
    )

    @property
    def changed(self) -> bool:
        return self.previous_readiness != self.current_readiness

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "previous_readiness": self.previous_readiness.value,
            "current_readiness": self.current_readiness.value,
            "transition": self.transition.value,
            "previous_reason": self.previous_reason.value,
            "current_reason": self.current_reason.value,
            "changed": self.changed,
        }
