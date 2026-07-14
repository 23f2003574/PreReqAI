from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_budget_decision import (
    ResearchWorkspaceConsumerProjectionBudgetDecision,
)

from .research_workspace_consumer_projection_budget_decision_reason import (
    ResearchWorkspaceConsumerProjectionBudgetDecisionReason,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


@dataclass
class ResearchWorkspaceConsumerProjectionBudgetAdmission:
    """
    Records one stage's budget admission
    decision, usable both by execution
    logic and by diagnostics.
    """

    stage_name: str

    decision: (
        ResearchWorkspaceConsumerProjectionBudgetDecision
    )

    reason: (
        ResearchWorkspaceConsumerProjectionBudgetDecisionReason
    )

    requirement: (
        ResearchWorkspaceConsumerProjectionStageRequirement
    )

    elapsed_ms: float

    remaining_ms: (
        float | None
    )

    minimum_remaining_budget_ms: float

    def to_dict(self):

        return {

            "stage_name":
                self.stage_name,

            "decision":
                self.decision.value,

            "reason":
                self.reason.value,

            "requirement":
                self.requirement.value,

            "elapsed_ms":
                self.elapsed_ms,

            "remaining_ms":
                self.remaining_ms,

            "minimum_remaining_budget_ms":
                self.minimum_remaining_budget_ms,
        }
