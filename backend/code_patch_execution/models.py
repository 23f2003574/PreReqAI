from dataclasses import dataclass
from datetime import datetime

SUCCEEDED = "SUCCEEDED"
ROLLED_BACK = "ROLLED_BACK"
STATUSES = frozenset({SUCCEEDED, ROLLED_BACK})


@dataclass(frozen=True)
class LLMCodePatchExecution:
    """One atomic application of a validated Commit #3 LLMCodePatchPlan to the
    actual generated output (the same CompilerJobResult.output backend.
    generated_code_review reviewed) it targets.

    changed_files is a tuple of the top-level output keys touched by this
    execution's operations -- the only record of what apply() actually
    wrote, and (together with the service's own private record of each
    operation's original value) the sole source rollback() reads to
    restore the generated output. A failed apply() raises before mutating
    anything and never creates an execution record, so status starts
    SUCCEEDED and only ever transitions to ROLLED_BACK.
    """

    execution_id: str
    plan_id: str
    status: str
    changed_files: tuple
    created_at: datetime
    completed_at: datetime
