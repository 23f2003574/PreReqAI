from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification(
    str,
    Enum,
):
    """
    A standardized domain label classifying a consumer projection's
    execution capability profile, exposed to downstream consumers.
    """

    STANDARD = (
        "standard"
    )

    RESTRICTED = (
        "restricted"
    )

    UNSUPPORTED = (
        "unsupported"
    )
