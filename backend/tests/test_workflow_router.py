from backend.workflows import (

    LearningIntent,

    LearningWorkflowRouter,

    WorkflowType,
)


def test_workflow_routing():

    router = (
        LearningWorkflowRouter()
    )

    assert (

        router.route(

            LearningIntent.EXPLAIN

        )

        == WorkflowType.EXPLANATION
    )

    assert (

        router.route(

            LearningIntent.QUIZ

        )

        == WorkflowType.QUIZ
    )

    assert (

        router.route(

            LearningIntent.UNKNOWN

        )

        == WorkflowType.DEFAULT
    )
