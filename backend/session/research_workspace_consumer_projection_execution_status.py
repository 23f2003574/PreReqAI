from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionStatus(
    str,
    Enum,
):
    """
    Describes the overall outcome of one
    completed consumer projection execution.

    A receipt should normally represent a completed
    projection execution with a valid final projection.
    If projection execution fails before a final projection
    exists, raise/return the existing execution failure
    rather than fabricating a successful-looking receipt.

    SUCCEEDED means the projection completed without
    consumer-relevant degradation.

    DEGRADED means the projection completed successfully,
    but one or more execution conditions reduced completeness,
    freshness, or preferred execution quality.
    """

    SUCCEEDED = (
        "succeeded"
    )

    DEGRADED = (
        "degraded"
    )
