from backend.session import (
    LearningIntent,
    WorkflowType,
)

from .explanation_workflow import (
    ExplanationWorkflow,
)

from .implementation_workflow import (
    ImplementationWorkflow,
)


class LearningWorkflowRouter:
    """
    Maps learner intents to the
    corresponding educational workflow.
    """

    def __init__(self):

        self.explanation = (
            ExplanationWorkflow()
        )

        self.implementation = (
            ImplementationWorkflow()
        )

    ROUTES = {

        LearningIntent.EXPLAIN:
            WorkflowType.EXPLANATION,

        LearningIntent.IMPLEMENT:
            WorkflowType.IMPLEMENTATION,

        LearningIntent.VISUALIZE:
            WorkflowType.VISUALIZATION,

        LearningIntent.COMPARE:
            WorkflowType.COMPARISON,

        LearningIntent.QUIZ:
            WorkflowType.QUIZ,

        LearningIntent.SUMMARIZE:
            WorkflowType.SUMMARY,

        LearningIntent.PREREQUISITES:
            WorkflowType.PREREQUISITE,
    }

    def route(

        self,

        intent: LearningIntent,

    ) -> WorkflowType:

        return self.ROUTES.get(

            intent,

            WorkflowType.DEFAULT,
        )

    def execute(

        self,

        workflow,

        session,

        paper,

        question,

    ):

        if workflow == WorkflowType.EXPLANATION:

            return self.explanation.execute(

                session,

                paper,

                question,
            )

        if workflow == WorkflowType.IMPLEMENTATION:

            return self.implementation.execute(

                session,

                paper,

                question,
            )

        return None
