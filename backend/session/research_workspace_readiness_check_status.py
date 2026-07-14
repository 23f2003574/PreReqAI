from enum import (
    Enum,
)


class ResearchWorkspaceReadinessCheckStatus(
    str,
    Enum,
):
    """
    Describes the outcome of one
    workspace readiness check.
    """

    PASS = (
        "pass"
    )

    WARNING = (
        "warning"
    )

    FAIL = (
        "fail"
    )
