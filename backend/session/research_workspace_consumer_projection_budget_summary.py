from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionBudgetSummary:
    """
    Compact summary of execution budget outcome.

    Describes what happened with budget behavior, not policy internals.
    Summarizes finalized budget decisions without leaking internal units
    unless the budget abstraction is stable and meaningful.

    Attributes:
        budgeted: Whether execution was budgeted
        admitted_stage_count: Number of optional stages admitted
        skipped_stage_count: Number of optional stages skipped
        exhausted: Whether budget was exhausted
    """

    budgeted: bool

    admitted_stage_count: int

    skipped_stage_count: int

    exhausted: bool
