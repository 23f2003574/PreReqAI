from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class LLMAgentStepExecution:
    """The immutable record of one attempt to execute one Commit #1 plan step.

    status reuses backend.llm.tool_execution's own vocabulary --
    SUCCEEDED, FAILED, DENIED, REJECTED, TIMED_OUT, CANCELLED -- rather
    than inventing a second one: every outcome except REJECTED is produced
    by asking the existing backend.llm.tool_orchestration.
    LLMToolCallingOrchestrationService to run the step and copying its
    decision's own status verbatim. REJECTED additionally covers the two
    gates this service owns and that pipeline never sees: a plan that
    fails Commit #2 validation, and a step whose dependency has not yet
    completed successfully -- both refused before the tool-calling
    pipeline is ever entered.

    result carries the Commit #6 normalized LLMToolResult when status is
    SUCCEEDED, and is None otherwise -- a failed, denied, rejected, or
    timed-out step is never reported as if it had a result. error explains
    a non-SUCCEEDED outcome and is None only when SUCCEEDED.
    """

    execution_id: str
    plan_id: str
    step_id: str
    status: str
    result: Any
    error: Optional[str]
    started_at: datetime
    completed_at: datetime
