from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LLMAgentCheckpoint:
    """An immutable snapshot of a Commit #4 plan execution's progress.

    completed_steps is a tuple of {"step_id", "execution_id"} pointers, in
    dependency order -- the execution_id of each step's own Commit #3
    LLMAgentStepExecution, never a copy of its result. current_step is the
    step_id that had not yet succeeded when this checkpoint was taken, or
    None once nothing is left to run. state reuses Commit #4's own
    LLMAgentPlanExecution status vocabulary unchanged, captured at the
    moment this checkpoint was written -- it is a historical fact and is
    never updated to track what the live execution does afterward.

    Like backend.llm.context_snapshot.LLMContextSnapshot, a checkpoint is
    written once and never edited: LLMAgentCheckpointService.save() is the
    only way to produce one.
    """

    checkpoint_id: str
    execution_id: str
    completed_steps: tuple
    current_step: Optional[str]
    state: str
    created_at: datetime
