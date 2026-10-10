from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionDiagnosticStatus(
    str,
    Enum,
):
    """
    Describes the outcome of one
    diagnostic input resolution or
    projection stage.
    """

    SUCCEEDED = (
        "succeeded"
    )

    DEGRADED = (
        "degraded"
    )

    FAILED = (
        "failed"
    )
