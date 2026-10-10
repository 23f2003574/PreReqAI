from backend.session import (
    LearningIntent,
    WorkflowType,
)

from .workflow_plan import (
    WorkflowPlan,
)


class LearningWorkflowPlanner:
    """
    Builds execution plans from detected
    learner intents.
    """

    def create_plan(

        self,

        intent: LearningIntent,

    ) -> WorkflowPlan:

        mapping = {

            LearningIntent.EXPLAIN:
                [
                    WorkflowType.EXPLANATION,
                    WorkflowType.EXAMPLE,
                    WorkflowType.FOLLOW_UP,
                ],

            LearningIntent.IMPLEMENT:
                [
                    WorkflowType.IMPLEMENTATION,
                    WorkflowType.EXAMPLE,
                    WorkflowType.FOLLOW_UP,
                ],

            LearningIntent.COMPARE:
                [
                    WorkflowType.COMPARISON,
                    WorkflowType.FOLLOW_UP,
                ],

            LearningIntent.VISUALIZE:
                [
                    WorkflowType.VISUALIZATION,
                    WorkflowType.FOLLOW_UP,
                ],

            LearningIntent.EXAMPLE:
                [
                    WorkflowType.EXAMPLE,
                    WorkflowType.FOLLOW_UP,
                ],

            LearningIntent.HINT:
                [
                    WorkflowType.HINT,
                ],

            LearningIntent.REFLECTION:
                [
                    WorkflowType.REFLECTION,
                ],

            LearningIntent.FOLLOW_UP:
                [
                    WorkflowType.FOLLOW_UP,
                ],
        }

        return WorkflowPlan(

            workflows=mapping.get(

                intent,

                [WorkflowType.DEFAULT],
            )
        )
