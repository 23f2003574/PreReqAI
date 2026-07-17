from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionEligibility(
    str,
    Enum,
):
    """
    Classifies whether a consumer projection, having already been
    evaluated for readiness, is eligible to be executed.
    """

    ELIGIBLE = (
        "eligible"
    )

    CONDITIONALLY_ELIGIBLE = (
        "conditionally_eligible"
    )

    INELIGIBLE = (
        "ineligible"
    )
