from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionVerdictReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution verdict.
    """

    AUTHORIZED = (
        "authorized"
    )

    APPROVAL_REQUIRED = (
        "approval_required"
    )

    AUTHORIZATION_DENIED = (
        "authorization_denied"
    )
