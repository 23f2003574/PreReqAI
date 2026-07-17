from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution authorization result.
    """

    GATE_OPEN = (
        "gate_open"
    )

    APPROVAL_PENDING = (
        "approval_pending"
    )

    GATE_CLOSED = (
        "gate_closed"
    )
