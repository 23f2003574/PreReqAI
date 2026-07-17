from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionDecisionReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution decision.
    """

    ELIGIBLE = (
        "eligible"
    )

    CONDITIONAL = (
        "conditional"
    )

    BLOCKED = (
        "blocked"
    )
