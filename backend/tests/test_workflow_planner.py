from backend.workflows import (

    LearningIntent,

    LearningWorkflowPlanner,

    WorkflowType,
)


def test_workflow_plan():

    planner = (
        LearningWorkflowPlanner()
    )

    plan = planner.create_plan(

        LearningIntent.EXPLAIN,
    )

    assert (

        plan.workflows[0]

        == WorkflowType.EXPLANATION
    )

    assert (

        WorkflowType.FOLLOW_UP

        in plan.workflows
    )
