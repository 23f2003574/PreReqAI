from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionPlanStage:
    """
    A planned execution stage, mandatory or optional.

    Attributes:
        name: Identifies the stage
        requirement: Whether the parent operation can omit this stage
        will_execute: Whether planning determined this stage can run
    """

    name: str

    requirement: (
        ResearchWorkspaceConsumerProjectionStageRequirement
    )

    will_execute: bool

    def to_dict(self):
        return {
            "name": self.name,
            "requirement": self.requirement.value,
            "will_execute": self.will_execute,
        }
