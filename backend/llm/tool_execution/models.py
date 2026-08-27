from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
DENIED = "DENIED"
REJECTED = "REJECTED"
STATUSES = frozenset({SUCCEEDED, FAILED, DENIED, REJECTED})


@dataclass(frozen=True)
class LLMToolExecution:
    """The single, immutable record of one attempt to run a Commit #3 plan.

    Every attempt is recorded, including the ones that never reached the
    tool at all, so a caller can always account for what the model asked
    for:

        REJECTED  the tool is unregistered, disabled, has no bound handler,
                  or the arguments failed revalidation at the execution
                  boundary -- nothing was invoked
        DENIED    Commit #4 authorization refused this subject -- nothing
                  was invoked
        FAILED    the tool itself raised
        SUCCEEDED the tool returned

    result carries whatever the tool returned, and is None for every status
    but SUCCEEDED. error is a short, secret-redacted explanation, and is
    None only when SUCCEEDED. No traceback is ever stored: frames carry
    local variables, which is exactly where credentials tend to sit.
    """

    execution_id: str
    plan_id: str
    tool_name: str
    status: str
    result: Any
    error: Optional[str]
    started_at: datetime
    completed_at: datetime
