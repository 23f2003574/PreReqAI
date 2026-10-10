from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionFreshnessStatus(
    str,
    Enum,
):
    """
    Classifies how current a resolved
    source's data is relative to its
    freshness policy.
    """

    FRESH = (
        "fresh"
    )

    STALE = (
        "stale"
    )

    UNUSABLE = (
        "unusable"
    )
