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

from .visualization_workflow import (
    VisualizationWorkflow,
)

from .comparison_workflow import (
    ComparisonWorkflow,
)

from .example_workflow import (
    ExampleWorkflow,
)

from .hint_workflow import (
    HintWorkflow,
)

from .reflection_workflow import (
    ReflectionWorkflow,
)

from .follow_up_workflow import (
    FollowUpWorkflow,
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

        self.visualization = (
            VisualizationWorkflow()
        )

        self.comparison = (
            ComparisonWorkflow()
        )

        self.example = (
            ExampleWorkflow()
        )

        self.hint = (
            HintWorkflow()
        )

        self.reflection = (
            ReflectionWorkflow()
        )

        self.follow_up = (
            FollowUpWorkflow()
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

        LearningIntent.EXAMPLE:
            WorkflowType.EXAMPLE,

        LearningIntent.HINT:
            WorkflowType.HINT,

        LearningIntent.REFLECTION:
            WorkflowType.REFLECTION,

        LearningIntent.FOLLOW_UP:
            WorkflowType.FOLLOW_UP,
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

        if workflow == WorkflowType.VISUALIZATION:

            return self.visualization.execute(

                session,

                paper,

                question,
            )

        if workflow == WorkflowType.COMPARISON:

            return self.comparison.execute(

                session,

                paper,

                question,
            )

        if workflow == WorkflowType.EXAMPLE:

            return self.example.execute(

                session,

                paper,

                question,
            )

        if workflow == WorkflowType.HINT:

            return self.hint.execute(

                session,

                paper,

                question,
            )

        if workflow == WorkflowType.REFLECTION:

            return self.reflection.execute(

                session,

                paper,

                question,
            )

        if workflow == WorkflowType.FOLLOW_UP:

            return self.follow_up.execute(

                session,

                paper,

                question,
            )

        raise NotImplementedError(

            f"{workflow.value} "
            "workflow is not implemented."
        )
