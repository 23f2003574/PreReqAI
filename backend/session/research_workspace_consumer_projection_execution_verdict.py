from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionVerdict(
    str,
    Enum,
):
    """
    Classifies the final policy outcome for a consumer projection's
    execution request, before any execution engine.
    """

    APPROVED = (
        "approved"
    )

    PENDING = (
        "pending"
    )

    REJECTED = (
        "rejected"
    )
