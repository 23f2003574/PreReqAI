from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerProjectionBudgetSnapshot:
    """
    A point-in-time read of a
    request-scoped execution budget.
    """

    soft_budget_ms: (
        float | None
    )

    elapsed_ms: float

    remaining_ms: (
        float | None
    )

    overrun_ms: float

    exhausted: bool

    def to_dict(self):

        return {

            "soft_budget_ms":
                self.soft_budget_ms,

            "elapsed_ms":
                self.elapsed_ms,

            "remaining_ms":
                self.remaining_ms,

            "overrun_ms":
                self.overrun_ms,

            "exhausted":
                self.exhausted,
        }
