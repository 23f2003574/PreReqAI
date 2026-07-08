from backend.workflows import (

    WorkflowExecutionResult,
)


def test_execution_result():

    result = (

        WorkflowExecutionResult()
    )

    result.executed_workflows.append(

        "explanation"
    )

    assert (

        len(

            result.executed_workflows

        )

        == 1
    )
