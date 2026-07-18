from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision(
    str,
    Enum,
):
    """
    A normalized policy decision derived from a consumer
    projection's execution capability, exposed to downstream
    consumers.
    """

    ACCEPT = (
        "accept"
    )

    REVIEW = (
        "review"
    )

    REJECT = (
        "reject"
    )
