from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


@dataclass
class ResearchWorkspaceConsumerProjectionStageBudgetPolicy:
    """
    Declares one stage's execution
    requirement and, for optional
    stages, the minimum remaining
    budget needed before it may begin.
    """

    stage_name: str

    requirement: (
        ResearchWorkspaceConsumerProjectionStageRequirement
    )

    minimum_remaining_budget_ms: float = 0.0

    def __post_init__(self):

        if (

            self.minimum_remaining_budget_ms

            < 0
        ):

            raise ValueError(

                "Stage budget policy "
                "minimum remaining budget "
                "cannot be negative"
            )

    def to_dict(self):

        return {

            "stage_name":
                self.stage_name,

            "requirement":
                self.requirement.value,

            "minimum_remaining_budget_ms":
                self.minimum_remaining_budget_ms,
        }
