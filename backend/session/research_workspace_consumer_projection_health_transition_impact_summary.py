from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_health_transition_impact import (
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
)

from .research_workspace_consumer_projection_health_transition_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary:
    """
    Compact, deterministic aggregate of the signal-level changes
    described by a Commit #5 health transition explanation.

    Attributes:
        projection_name: Projection name reused from the explanation
        previous_execution_id: Execution ID reused from the explanation
        current_execution_id: Execution ID reused from the explanation
        transition: Health transition kind reused from the explanation
        impact: Directional classification of the signal-level change
        appeared_count: Number of newly appeared signal codes
        resolved_count: Number of resolved signal codes
        persistent_count: Number of persistent signal codes
        severity_increase_count: Number of persistent signals that escalated
        severity_decrease_count: Number of persistent signals that de-escalated
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

    appeared_count: int

    resolved_count: int

    persistent_count: int

    severity_increase_count: int

    severity_decrease_count: int

    @property
    def changed_signal_count(self) -> int:
        return (
            self.appeared_count
            + self.resolved_count
            + self.severity_increase_count
            + self.severity_decrease_count
        )

    def to_dict(self):
        """
        Serialize the impact summary to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "transition": self.transition.value,
            "impact": self.impact.value,
            "appeared_count": self.appeared_count,
            "resolved_count": self.resolved_count,
            "persistent_count": self.persistent_count,
            "severity_increase_count": self.severity_increase_count,
            "severity_decrease_count": self.severity_decrease_count,
            "changed_signal_count": self.changed_signal_count,
        }
