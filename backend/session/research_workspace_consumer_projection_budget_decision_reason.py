from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionBudgetDecisionReason(
    str,
    Enum,
):
    """
    Explains why a budget admission
    decision was reached.
    """

    MANDATORY = (
        "mandatory"
    )

    WITHIN_BUDGET = (
        "within_budget"
    )

    INSUFFICIENT_REMAINING_BUDGET = (
        "insufficient_remaining_budget"
    )

    BUDGET_EXHAUSTED = (
        "budget_exhausted"
    )
