from .research_workspace_consumer_projection_execution_budget import (
    ResearchWorkspaceConsumerProjectionExecutionBudget,
)

from .research_workspace_monotonic_clock import (
    ResearchWorkspaceMonotonicClock,
)


class ResearchWorkspaceConsumerProjectionExecutionBudgetFactory:
    """
    Application-scoped factory that
    creates a fresh, operation-scoped
    execution budget for one consumer
    projection operation.
    """

    def __init__(

        self,

        clock=None,

    ):

        self._clock = (

            clock

            or ResearchWorkspaceMonotonicClock()
        )

    def create(

        self,

        *,

        policy,

    ):

        return (

            ResearchWorkspaceConsumerProjectionExecutionBudget(

                policy=policy,

                clock=self._clock,
            )
        )
