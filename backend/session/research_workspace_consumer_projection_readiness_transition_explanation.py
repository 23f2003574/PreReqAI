from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_issue_change import (
    ResearchWorkspaceConsumerProjectionReadinessIssueChange,
)

from .research_workspace_consumer_projection_readiness_transition import (
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessTransitionExplanation:
    """
    Compact, machine-readable explanation of which readiness issue
    codes changed between two evaluations, complementing a Commit #4
    readiness transition.

    Answers which issue codes appeared, resolved, or persisted - not
    why in natural language, and not a recalculation of readiness or
    the transition classification themselves.

    Attributes:
        projection_name: Name of the compared projection
        transition: The readiness transition this explanation describes
        appeared_issues: Codes present in current but not previous
        resolved_issues: Codes present in previous but not current
        persistent_issues: Codes present in both reports
        changes: Per-code presence comparisons, stable-ordered
    """

    projection_name: str

    transition: (
        ResearchWorkspaceConsumerProjectionReadinessTransition
    )

    appeared_issues: tuple[
        str,
        ...,
    ]

    resolved_issues: tuple[
        str,
        ...,
    ]

    persistent_issues: tuple[
        str,
        ...,
    ]

    changes: tuple[
        ResearchWorkspaceConsumerProjectionReadinessIssueChange,
        ...,
    ]

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "transition": self.transition.value,
            "appeared_issues": list(self.appeared_issues),
            "resolved_issues": list(self.resolved_issues),
            "persistent_issues": list(self.persistent_issues),
            "changes": [
                change.to_dict() for change in self.changes
            ],
        }
