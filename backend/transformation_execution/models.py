from dataclasses import dataclass
from datetime import datetime

SUCCEEDED = "SUCCEEDED"
ROLLED_BACK = "ROLLED_BACK"
STATUSES = frozenset({SUCCEEDED, ROLLED_BACK})


@dataclass(frozen=True)
class LLMTransformationExecution:
    """One atomic application of an approved, validated LLMTransformationDiff to notebook source.

    applied_cells is a tuple of {"cell_index", "original_source",
    "applied_source"} dicts, one per mutated cell -- the only record of
    what apply() actually wrote, and the sole source rollback() reads to
    restore original_source. A failed apply() raises before mutating
    anything and never creates an execution record, so status starts
    SUCCEEDED and only ever transitions to ROLLED_BACK.
    """

    execution_id: str
    diff_id: str
    status: str
    applied_cells: tuple
    created_at: datetime
    completed_at: datetime
