from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_health_signal_change import (
    ResearchWorkspaceConsumerProjectionHealthSignalChange,
)

from .research_workspace_consumer_projection_health_transition_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
)

from .research_workspace_consumer_projection_quality_signal_code import (
    ResearchWorkspaceConsumerProjectionQualitySignalCode,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionHealthTransitionExplanation:
    """
    Compact, machine-readable explanation of which quality signals
    changed between two executions, complementing a Commit #4 health
    transition.

    Answers which conditions appeared, resolved, persisted, or
    changed severity - not why in natural language, and not a
    recalculation of the transition or health classification
    themselves.

    Attributes:
        projection_name: Name of the compared projection
        previous_execution_id: Execution ID of the previous report
        current_execution_id: Execution ID of the current report
        transition: The health transition this explanation describes
        appeared_signals: Codes present in current but not previous
        resolved_signals: Codes present in previous but not current
        persistent_signals: Codes present in both reports
        severity_changes: Per-code severity comparisons, stable-ordered
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    transition: (
        ResearchWorkspaceConsumerProjectionHealthTransitionKind
    )

    appeared_signals: tuple[
        ResearchWorkspaceConsumerProjectionQualitySignalCode,
        ...,
    ]

    resolved_signals: tuple[
        ResearchWorkspaceConsumerProjectionQualitySignalCode,
        ...,
    ]

    persistent_signals: tuple[
        ResearchWorkspaceConsumerProjectionQualitySignalCode,
        ...,
    ]

    severity_changes: tuple[
        ResearchWorkspaceConsumerProjectionHealthSignalChange,
        ...,
    ]

    def to_dict(self):
        """
        Serialize the explanation to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "transition": self.transition.value,
            "appeared_signals": [
                code.value for code in self.appeared_signals
            ],
            "resolved_signals": [
                code.value for code in self.resolved_signals
            ],
            "persistent_signals": [
                code.value for code in self.persistent_signals
            ],
            "severity_changes": [
                {
                    "code": change.code.value,
                    "previous_severity": (
                        change.previous_severity.value
                        if change.previous_severity
                        else None
                    ),
                    "current_severity": (
                        change.current_severity.value
                        if change.current_severity
                        else None
                    ),
                }
                for change in self.severity_changes
            ],
        }
