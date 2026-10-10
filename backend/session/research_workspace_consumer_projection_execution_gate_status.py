from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionGateStatus(
    str,
    Enum,
):
    """
    Classifies whether execution may proceed for a consumer
    projection, having already been resolved to an execution
    decision.
    """

    OPEN = (
        "open"
    )

    CONDITIONAL = (
        "conditional"
    )

    CLOSED = (
        "closed"
    )
