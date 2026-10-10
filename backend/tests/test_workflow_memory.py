from backend.workflows import (
    WorkflowMemory,
    WorkflowType,
)


def test_workflow_memory():

    memory = WorkflowMemory()

    memory.add(

        WorkflowType.EXPLANATION,

        "Attention",
    )

    assert (

        memory.has_completed(

            WorkflowType.EXPLANATION,

            "Attention",
        )

        is True
    )
