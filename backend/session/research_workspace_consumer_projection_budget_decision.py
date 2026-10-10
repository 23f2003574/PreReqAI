from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionBudgetDecision(
    str,
    Enum,
):
    """
    Whether a stage was admitted to
    execute under the current
    request-scoped execution budget.
    """

    EXECUTE = (
        "execute"
    )

    SKIP = (
        "skip"
    )
