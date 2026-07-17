from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionLifecycleState(
    str,
    Enum,
):
    """
    Classifies the normalized lifecycle state of a consumer
    projection's execution outcome, exposed to downstream
    orchestration.
    """

    READY = (
        "ready"
    )

    WAITING = (
        "waiting"
    )

    BLOCKED = (
        "blocked"
    )
