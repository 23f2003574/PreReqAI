from .action_execution_result import (
    ActionExecutionResult,
)
from .object_action import (
    ObjectAction,
)
from .research_object import (
    ResearchObject,
)


class ConceptActionEngine:
    """
    Executes educational actions for
    research concepts by dispatching
    them to the learning workflow system.

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
    def _action_mapping():

        from backend.session import (
            WorkflowType,
        )

        return {
            ObjectAction.EXPLAIN: WorkflowType.EXPLANATION,
            ObjectAction.VISUALIZE: WorkflowType.VISUALIZATION,
            ObjectAction.IMPLEMENT: WorkflowType.IMPLEMENTATION,
            ObjectAction.COMPARE: WorkflowType.COMPARISON,
            ObjectAction.QUIZ: WorkflowType.QUIZ,
        }

    def workflow_for(
        self,
        action: ObjectAction,
    ):

        return self._action_mapping().get(
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

        return ActionExecutionResult(
            object_id=research_object.id,
            action=action.value,
            workflow=workflow.value,
            response=response,
        )
