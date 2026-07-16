from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_readiness_priority import (
    ResearchWorkspaceConsumerProjectionReadinessPriority,
)

from .research_workspace_consumer_projection_readiness_recommendation import (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReadinessDirective:
    """
    Finalized, immutable advisory response decision combining a
    Commit #8 readiness recommendation and a Commit #9 readiness
    priority report.

    This is a portable description of a decision, not an action -
    it does not create a task, send an alert, trigger a retry, or
    perform remediation. It carries no timestamp, mutable status,
    acknowledgement state, completion state, assigned user, or retry
    counter; those belong to future workflow or persistence layers.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        recommendation: Recommendation reused from the recommendation report
        priority: Priority reused from the priority report
    """

    projection_name: str

    recommendation: (
        ResearchWorkspaceConsumerProjectionReadinessRecommendation
    )

    priority: (
        ResearchWorkspaceConsumerProjectionReadinessPriority
    )

    @property
    def action_required(self) -> bool:
        # Mirrors the authoritative semantics already defined on
        # ResearchWorkspaceConsumerProjectionReadinessRecommendationReport
        # (Commit #8) - action requirement is derived from the
        # recommendation, never from priority alone.
        return self.recommendation in {
            ResearchWorkspaceConsumerProjectionReadinessRecommendation.REVIEW_CHANGES,
            ResearchWorkspaceConsumerProjectionReadinessRecommendation.INVESTIGATE,
            ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION,
        }

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "recommendation": self.recommendation.value,
            "priority": self.priority.value,
            "action_required": self.action_required,
        }
