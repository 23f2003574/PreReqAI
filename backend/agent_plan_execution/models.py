from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LLMAgentPlanExecution:
    """The immutable, evolving record of one attempt to run a Commit #1 plan end to end.

    status reuses backend.llm.tool_execution's own vocabulary -- RUNNING is
    the only non-terminal value, and SUCCEEDED/FAILED/REJECTED/CANCELLED
    keep exactly the meaning that module gives them at the tool-call level,
    read up one level to the whole plan:

        REJECTED   the plan failed Commit #2 validation; no step ever ran
        RUNNING    steps are being executed in dependency order
        SUCCEEDED  every step completed successfully
        FAILED     a step did not succeed, and execution stopped there
        CANCELLED  cancel() was requested and honoured between two steps

    completed_steps is the step_ids that succeeded, in the order they were
    run -- the dependency order Commit #4 computed, not the plan's
    declaration order. failed_step is the one step_id that stopped
    execution, and is None for every status but FAILED. This record never
    duplicates a step's own outcome -- that stays exactly Commit #3's
    LLMAgentStepExecution, reachable via LLMAgentPlanExecutionService.steps().
    """

    execution_id: str
    plan_id: str
    status: str
    completed_steps: list
    failed_step: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
