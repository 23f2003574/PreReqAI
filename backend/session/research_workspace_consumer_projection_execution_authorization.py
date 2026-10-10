from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionAuthorization(
    str,
    Enum,
):
    """
    Classifies whether a consumer projection's execution request
    is authorized to pass through the execution gate.
    """

    AUTHORIZED = (
        "authorized"
    )

    CONDITIONAL = (
        "conditional"
    )

    DENIED = (
        "denied"
    )
