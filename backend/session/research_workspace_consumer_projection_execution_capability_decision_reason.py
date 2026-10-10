from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution capability decision.
    """

    STANDARD_CAPABILITY = (
        "standard_capability"
    )

    RESTRICTED_CAPABILITY = (
        "restricted_capability"
    )

    UNSUPPORTED_CAPABILITY = (
        "unsupported_capability"
    )
