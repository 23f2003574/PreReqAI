from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionLifecycleReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution lifecycle state.
    """

    READY_FOR_EXECUTION = (
        "ready_for_execution"
    )

    WAITING_FOR_APPROVAL = (
        "waiting_for_approval"
    )

    EXECUTION_BLOCKED = (
        "execution_blocked"
    )
