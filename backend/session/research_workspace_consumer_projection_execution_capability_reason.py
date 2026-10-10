from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution capability.
    """

    READY = (
        "ready"
    )

    APPROVAL_REQUIRED = (
        "approval_required"
    )

    EXECUTION_BLOCKED = (
        "execution_blocked"
    )
