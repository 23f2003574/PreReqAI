from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessRecommendation(
    str,
    Enum,
):
    """
    Generic recommended response posture derived from a readiness
    operational assessment.

    Advisory only - never itself an execution, retry, or policy
    decision.
    """

    NO_ACTION = (
        "no_action"
    )

    CONTINUE_MONITORING = (
        "continue_monitoring"
    )

    REVIEW_CHANGES = (
        "review_changes"
    )

    INVESTIGATE = (
        "investigate"
    )

    UNBLOCK_EXECUTION = (
        "unblock_execution"
    )
