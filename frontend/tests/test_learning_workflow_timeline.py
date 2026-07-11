from frontend.src.timeline import (

    LearningWorkflowTimeline,

    TimelineStepStatus,
)


def test_loads_workflow_timeline():

    timeline = (
        LearningWorkflowTimeline()
    )

    steps = timeline.load(

        [

            "Explain",

            "Visualize",

            "Quiz",
        ]
    )

    assert (

        len(steps)

        == 3
    )

    assert (

        steps[0].title

        == "Explain"
    )

    assert (

        steps[0].status

        == TimelineStepStatus.PENDING
    )


def test_activates_workflow_step():

    timeline = (
        LearningWorkflowTimeline()
    )

    timeline.load(

        [

            "Explain",

            "Visualize",
        ]
    )

    selected = timeline.activate(

        "step-1"
    )

    assert (

        selected.status

        == TimelineStepStatus.ACTIVE
    )

    assert (

        timeline.active_step_id

        == "step-1"
    )


def test_completes_workflow_step():

    timeline = (
        LearningWorkflowTimeline()
    )

    timeline.load(

        [
            "Explain",
        ]
    )

    timeline.activate(

        "step-1"
    )

    completed = timeline.complete(

        "step-1"
    )

    assert (

        completed.status

        == TimelineStepStatus.COMPLETED
    )

    assert (

        timeline.active_step_id

        is None
    )


def test_only_one_step_remains_active():

    timeline = (
        LearningWorkflowTimeline()
    )

    timeline.load(

        [

            "Explain",

            "Visualize",
        ]
    )

    timeline.activate(

        "step-1"
    )

    timeline.activate(

        "step-2"
    )

    assert (

        timeline.get(
            "step-1"
        ).status

        == TimelineStepStatus.PENDING
    )

    assert (

        timeline.get(
            "step-2"
        ).status

        == TimelineStepStatus.ACTIVE
    )
