from dataclasses import (
    dataclass,
    field,
)

from .research_repair_action import (
    ResearchRepairAction,
)

from .research_repair_risk import (
    ResearchRepairRisk,
)


@dataclass
class ResearchRepairPlan:
    """
    Contains proposed repair actions for
    a workspace integrity report.
    """

    actions: list[
        ResearchRepairAction
    ] = field(
        default_factory=list,
    )

    @property
    def safe_actions(self):

        return [

            action

            for action

            in self.actions

            if (

                action.risk

                == ResearchRepairRisk
                .SAFE
            )
        ]

    @property
    def review_actions(self):

        return [

            action

            for action

            in self.actions

            if (

                action.risk

                == ResearchRepairRisk
                .REVIEW
            )
        ]

    @property
    def destructive_actions(self):

        return [

            action

            for action

            in self.actions

            if (

                action.risk

                == ResearchRepairRisk
                .DESTRUCTIVE
            )
        ]

    def to_dict(self):

        return {

            "total_actions":
                len(
                    self.actions
                ),

            "safe_actions":
                len(
                    self.safe_actions
                ),

            "review_actions":
                len(
                    self.review_actions
                ),

            "destructive_actions":
                len(
                    self.destructive_actions
                ),

            "actions": [

                action.to_dict()

                for action

                in self.actions
            ],
        }
