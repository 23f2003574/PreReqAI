from .action_execution_result import (
    ActionExecutionResult,
)
from .object_action import (
    ObjectAction,
)
from .research_object import (
    ResearchObject,
)


class ObjectActionEngine:
    """
    Base engine that executes educational
    actions for a research object type by
    dispatching them to the learning
    workflow system. Subclasses only need
    to declare which workflow backs each
    action via action_mapping().

    Imports backend.workflows/backend.session
    lazily: backend.models.paper already
    imports ResearchObject from this package,
    so importing them at module level here
    would create a circular import.
    """

    def __init__(self, workflow_router=None):

        from backend.workflows import (
            LearningWorkflowRouter,
        )

        self.workflow_router = (
            workflow_router
            or LearningWorkflowRouter()
        )

    @staticmethod
    def action_mapping():

        raise NotImplementedError

    def workflow_for(
        self,
        action: ObjectAction,
    ):

        return self.action_mapping().get(
            action,
        )

    def execute(
        self,
        research_object: ResearchObject,
        action: ObjectAction,
        session,
        paper,
    ) -> ActionExecutionResult:
        """
        Runs the learning workflow behind
        an action and returns the real
        tutoring response alongside it,
        not just the workflow's name.
        """

        workflow = self.workflow_for(
            action,
        )

        if workflow is None:

            return ActionExecutionResult(
                object_id=research_object.id,
                action=action.value,
                workflow=None,
            )

        question = (
            f"{action.value.capitalize()} "
            f"{research_object.title}"
        )

        try:

            response = (
                self.workflow_router.execute(
                    workflow,
                    session,
                    paper,
                    question,
                )
            )

        except NotImplementedError:

            response = None

        if response is not None:

            workflow_memory = getattr(
                session,
                "workflow_memory",
                None,
            )

            if workflow_memory is not None:

                workflow_memory.add(
                    workflow,
                    research_object.title,
                )

        return ActionExecutionResult(
            object_id=research_object.id,
            action=action.value,
            workflow=workflow.value,
            response=response,
        )
