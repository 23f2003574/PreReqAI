from .learning_intent import (
    LearningIntent,
)

from .workflow_type import (
    WorkflowType,
)


class LearningWorkflowRouter:
    """
    Maps learner intents to the
    corresponding educational workflow.
    """

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
