from backend.interaction import (
    InteractionOrchestrator,
    InteractionPlan,
)
from backend.pipeline import (
    InteractiveObjectPipeline,
)
from backend.workflows import (
    LearningWorkflowRouter,
)


class InteractiveResearchEngine:
    """
    High-level engine responsible for
    interactive educational experiences.
    Exposes both single-action interactions
    (via the pipeline) and multi-action
    plans (via the orchestrator) behind
    one interface, sharing a single
    LearningWorkflowRouter between them.
    """

    def __init__(self, workflow_router=None):

        self.workflow_router = (
            workflow_router
            or LearningWorkflowRouter()
        )

        self.pipeline = (
            InteractiveObjectPipeline(
                self.workflow_router,
            )
        )

        self.orchestrator = (
            InteractionOrchestrator(
                self.workflow_router,
            )
        )

    def interact(
        self,
        session,
        research_object,
        action,
    ):

        return self.pipeline.execute(
            session,
            research_object,
            action,
        )

    def interact_many(
        self,
        session,
        research_object,
        plan: InteractionPlan,
    ):

        return self.orchestrator.execute(
            session,
            research_object,
            plan,
        )
