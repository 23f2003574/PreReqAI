from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority(
    str,
    Enum,
):
    """
    Relative response priority for a Commit #8 response recommendation.

    NONE means no response is required.

    LOW means continued observation is sufficient.

    MEDIUM means review should occur through normal workflow.

    HIGH means investigation should be prioritized.

    URGENT means the transition requires prompt review.

    This is a relative classification only - it carries no timing
    guarantee (e.g. "within 5 minutes", "same day"). Deployment-
    specific service-level policy belongs to a future layer, not here.
    """

    NONE = (
        "none"
    )

    LOW = (
        "low"
    )

    MEDIUM = (
        "medium"
    )

    HIGH = (
        "high"
    )

    URGENT = (
        "urgent"
    )
