from .research_workspace_consumer_projection_budget_admission import (
    ResearchWorkspaceConsumerProjectionBudgetAdmission,
)

from .research_workspace_consumer_projection_budget_decision import (
    ResearchWorkspaceConsumerProjectionBudgetDecision,
)

from .research_workspace_consumer_projection_budget_decision_reason import (
    ResearchWorkspaceConsumerProjectionBudgetDecisionReason,
)

from .research_workspace_consumer_projection_budget_snapshot import (
    ResearchWorkspaceConsumerProjectionBudgetSnapshot,
)

from .research_workspace_consumer_projection_stage_requirement import (
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


class ResearchWorkspaceConsumerProjectionExecutionBudget:
    """
    Request-scoped, cooperative soft
    execution budget for one consumer
    projection operation. Governs
    whether optional work should begin;
    it cannot interrupt work already
    running.
    """

    def __init__(

        self,

        *,

        policy,

        clock,

    ):

        self.policy = policy

        self._clock = clock

        self._started_at = (
            clock.now()
        )

    def snapshot(self):

        soft_budget_ms = (

            self.policy.soft_budget_ms

            if self.policy is not None

            else None
        )

        elapsed_ms = (

            (

                self._clock.now()

                - self._started_at
            )

            * 1000
        )

        if soft_budget_ms is None:

            return (

                ResearchWorkspaceConsumerProjectionBudgetSnapshot(

                    soft_budget_ms=None,

                    elapsed_ms=(
                        elapsed_ms
                    ),

                    remaining_ms=None,

                    overrun_ms=0.0,

                    exhausted=False,
                )
            )

        remaining_ms = max(

            0.0,

            soft_budget_ms

            - elapsed_ms,
        )

        overrun_ms = max(

            0.0,

            elapsed_ms

            - soft_budget_ms,
        )

        return (

            ResearchWorkspaceConsumerProjectionBudgetSnapshot(

                soft_budget_ms=(
                    soft_budget_ms
                ),

                elapsed_ms=(
                    elapsed_ms
                ),

                remaining_ms=(
                    remaining_ms
                ),

                overrun_ms=(
                    overrun_ms
                ),

                exhausted=(
                    remaining_ms

                    <= 0.0
                ),
            )
        )

    def evaluate(

        self,

        *,

        stage_name,

        requirement,

        minimum_remaining_budget_ms,

    ):

        current = self.snapshot()

        if (

            requirement

            == ResearchWorkspaceConsumerProjectionStageRequirement
            .MANDATORY
        ):

            decision = (

                ResearchWorkspaceConsumerProjectionBudgetDecision
                .EXECUTE
            )

            reason = (

                ResearchWorkspaceConsumerProjectionBudgetDecisionReason
                .MANDATORY
            )

        elif current.soft_budget_ms is None:

            decision = (

                ResearchWorkspaceConsumerProjectionBudgetDecision
                .EXECUTE
            )

            reason = (

                ResearchWorkspaceConsumerProjectionBudgetDecisionReason
                .WITHIN_BUDGET
            )

        elif current.remaining_ms <= 0.0:

            decision = (

                ResearchWorkspaceConsumerProjectionBudgetDecision
                .SKIP
            )

            reason = (

                ResearchWorkspaceConsumerProjectionBudgetDecisionReason
                .BUDGET_EXHAUSTED
            )

        elif (

            current.remaining_ms

            < minimum_remaining_budget_ms
        ):

            decision = (

                ResearchWorkspaceConsumerProjectionBudgetDecision
                .SKIP
            )

            reason = (

                ResearchWorkspaceConsumerProjectionBudgetDecisionReason
                .INSUFFICIENT_REMAINING_BUDGET
            )

        else:

            decision = (

                ResearchWorkspaceConsumerProjectionBudgetDecision
                .EXECUTE
            )

            reason = (

                ResearchWorkspaceConsumerProjectionBudgetDecisionReason
                .WITHIN_BUDGET
            )

        return (

            ResearchWorkspaceConsumerProjectionBudgetAdmission(

                stage_name=stage_name,

                decision=decision,

                reason=reason,

                requirement=requirement,

                elapsed_ms=(
                    current.elapsed_ms
                ),

                remaining_ms=(
                    current.remaining_ms
                ),

                minimum_remaining_budget_ms=(
                    minimum_remaining_budget_ms
                ),
            )
        )
