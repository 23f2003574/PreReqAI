from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionOutcome(
    str,
    Enum,
):
    """
    Classifies the final normalized execution state of a consumer
    projection, exposed to downstream consumers.
    """

    READY = (
        "ready"
    )

    PENDING = (
        "pending"
    )

    BLOCKED = (
        "blocked"
    )
