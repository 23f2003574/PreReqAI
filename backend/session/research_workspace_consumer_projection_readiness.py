from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadiness(
    str,
    Enum,
):
    """
    Classifies whether a planned consumer
    projection execution can proceed.
    """

    READY = (
        "ready"
    )

    BLOCKED = (
        "blocked"
    )

    DEGRADED_READY = (
        "degraded_ready"
    )
