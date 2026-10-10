from .research_workspace_consumer_projection_budget_decision import (
    ResearchWorkspaceConsumerProjectionBudgetDecision,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


class ResearchWorkspaceConsumerProjectionExecutionCoordinator:
    """
    Evaluates budget admission for one
    named stage immediately before it
    would execute, and records the
    decision to diagnostics when present.

    Duration/success/failure recording
    for the stage itself remains the
    stage's own responsibility (as
    established in Commit #8) — the
    coordinator only decides whether the
    stage should be attempted at all.
    """

    def __init__(

        self,

        *,

        budget=None,

        diagnostics=None,

    ):

        self.budget = budget

        self.diagnostics = diagnostics

    def execute_stage(

        self,

        *,

        name,

        operation,

        on_skip=None,

    ):

        if self.budget is None:

            return operation()

        stage_policy = None

        if self.budget.policy is not None:

            stage_policy = (

                self.budget.policy
                .get_stage_policy(
                    name
                )
            )

        requirement = (

            stage_policy.requirement

            if stage_policy is not None

            else (

                ResearchWorkspaceConsumerProjectionStageRequirement
                .MANDATORY
            )
        )

        minimum_remaining_budget_ms = (

            stage_policy
            .minimum_remaining_budget_ms

            if stage_policy is not None

            else 0.0
        )

        admission = (

            self.budget.evaluate(

                stage_name=name,

                requirement=requirement,

                minimum_remaining_budget_ms=(
                    minimum_remaining_budget_ms
                ),
            )
        )

        if self.diagnostics is not None:

            self.diagnostics.record_budget_admission(
                admission
            )

        if (

            admission.decision

            == ResearchWorkspaceConsumerProjectionBudgetDecision
            .SKIP
        ):

            if on_skip is not None:

                return on_skip()

            return None

        return operation()
