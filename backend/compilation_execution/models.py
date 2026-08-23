from dataclasses import dataclass
from datetime import datetime
from typing import Optional


SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
STATUSES = frozenset({SUCCEEDED, FAILED})


@dataclass(frozen=True)
class LLMCompilationExecution:
    """One attempt to hand a Commit #11 plan to the existing compiler.

    compiler_job_id is the id the compiler itself assigned, preserved
    verbatim so the plan and the compiler's own job can always be traced
    back to each other -- it may be None if the compiler failed before
    assigning one. status always reflects the compiler's own verdict
    (SUCCEEDED/FAILED); this bridge never overrides it.
    """

    execution_id: str
    plan_id: str
    compiler_job_id: Optional[str]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
