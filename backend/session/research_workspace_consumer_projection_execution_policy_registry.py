from .research_workspace_consumer_projection_execution_policy import (
    ResearchWorkspaceConsumerProjectionExecutionPolicy,
)

from .research_workspace_consumer_projection_stage_budget_policy import (
    ResearchWorkspaceConsumerProjectionStageBudgetPolicy,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


DEFAULT_CONSUMER_PROJECTION_POLICIES = (

    ResearchWorkspaceConsumerProjectionExecutionPolicy(

        operation_name="workspace.bootstrap",

        soft_budget_ms=500.0,

        stage_policies=[

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.bootstrap.overview"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.attention.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=150.0,
            ),

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.actions.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=75.0,
            ),

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.bootstrap.recent_sessions"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=50.0,
            ),

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.bootstrap.recent_activity"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .OPTIONAL
                ),

                minimum_remaining_budget_ms=40.0,
            ),

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.bootstrap.assemble"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),
        ],
    ),

    ResearchWorkspaceConsumerProjectionExecutionPolicy(

        operation_name="workspace.attention",

        soft_budget_ms=None,

        stage_policies=[

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.attention.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),
        ],
    ),

    ResearchWorkspaceConsumerProjectionExecutionPolicy(

        operation_name="workspace.actions",

        soft_budget_ms=None,

        stage_policies=[

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "workspace.actions.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),
        ],
    ),

    ResearchWorkspaceConsumerProjectionExecutionPolicy(

        operation_name="session.actions",

        soft_budget_ms=None,

        stage_policies=[

            ResearchWorkspaceConsumerProjectionStageBudgetPolicy(

                stage_name=(
                    "session.actions.project"
                ),

                requirement=(

                    ResearchWorkspaceConsumerProjectionStageRequirement
                    .MANDATORY
                ),
            ),
        ],
    ),
)


class ResearchWorkspaceConsumerProjectionExecutionPolicyRegistry:
    """
    Owns the authoritative, explicit
    execution policy for each consumer
    projection operation.
    """

    def __init__(

        self,

        policies=None,

    ):

        policies = (

            policies

            or DEFAULT_CONSUMER_PROJECTION_POLICIES
        )

        seen_operation_names = set()

        for policy in policies:

            if (

                policy.operation_name

                in seen_operation_names
            ):

                raise ValueError(

                    "Duplicate execution "
                    "policy operation name: "
                    f"{policy.operation_name}"
                )

            seen_operation_names.add(
                policy.operation_name
            )

        self._policies = {

            policy.operation_name:
                policy

            for policy

            in policies
        }

    def get_policy(

        self,

        operation_name,

    ):

        return (

            self._policies
            .get(
                operation_name
            )
        )

    def list_policies(self):

        return list(

            self._policies
            .values()
        )
