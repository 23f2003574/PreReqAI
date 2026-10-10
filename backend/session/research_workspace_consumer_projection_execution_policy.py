from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_stage_budget_policy import (
    ResearchWorkspaceConsumerProjectionStageBudgetPolicy,
)


@dataclass
class ResearchWorkspaceConsumerProjectionExecutionPolicy:
    """
    Declares one consumer operation's
    soft execution budget and the
    per-stage requirements that apply
    within it. Operational configuration,
    not a consumer contract.
    """

    operation_name: str

    soft_budget_ms: (
        float | None
    )

    stage_policies: list[
        ResearchWorkspaceConsumerProjectionStageBudgetPolicy
    ] = field(
        default_factory=list,
    )

    def __post_init__(self):

        if (

            self.soft_budget_ms

            is not None

            and self.soft_budget_ms < 0
        ):

            raise ValueError(

                "Execution policy soft "
                "budget cannot be negative"
            )

        seen_stage_names = set()

        for stage_policy in (
            self.stage_policies
        ):

            if (

                stage_policy.stage_name

                in seen_stage_names
            ):

                raise ValueError(

                    "Duplicate stage name "
                    f"'{stage_policy.stage_name}' "
                    "in execution policy "
                    f"'{self.operation_name}'"
                )

            seen_stage_names.add(
                stage_policy.stage_name
            )

    def get_stage_policy(

        self,

        stage_name,

    ):

        for stage_policy in (
            self.stage_policies
        ):

            if (

                stage_policy.stage_name

                == stage_name
            ):

                return stage_policy

        return None

    def to_dict(self):

        return {

            "operation_name":
                self.operation_name,

            "soft_budget_ms":
                self.soft_budget_ms,

            "stage_policies": [

                stage_policy.to_dict()

                for stage_policy

                in self.stage_policies
            ],
        }
