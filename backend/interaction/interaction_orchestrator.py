from .interaction_dispatcher import (
    InteractionDispatcher,
)
from .interaction_plan import (
    InteractionPlan,
)


class InteractionOrchestrator:
    """
    Coordinates multiple educational
    interactions for a research object,
    so a sequence like Explain then
    Visualize then Quiz executes as one
    ordered learning experience instead
    of unrelated dispatcher calls.
    """

    def __init__(self, workflow_router=None):

        self.dispatcher = (
            InteractionDispatcher(
                workflow_router,
            )
        )

    def execute(
        self,
        session,
        research_object,
        plan: InteractionPlan,
    ):

        responses = []

        for action in plan.actions:

            response = (
                self.dispatcher.dispatch(
                    research_object,
                    action,
                    session,
                    session.paper,
                )
            )

            responses.append(response)

        return responses
