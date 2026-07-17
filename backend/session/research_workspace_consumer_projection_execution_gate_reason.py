from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionGateReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution gate status.
    """

    EXECUTION_ALLOWED = (
        "execution_allowed"
    )

    APPROVAL_REQUIRED = (
        "approval_required"
    )

    EXECUTION_BLOCKED = (
        "execution_blocked"
    )
