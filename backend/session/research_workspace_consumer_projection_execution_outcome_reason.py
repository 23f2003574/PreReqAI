from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionOutcomeReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution outcome.
    """

    EXECUTION_APPROVED = (
        "execution_approved"
    )

    APPROVAL_PENDING = (
        "approval_pending"
    )

    EXECUTION_REJECTED = (
        "execution_rejected"
    )
