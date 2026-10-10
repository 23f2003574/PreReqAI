from datetime import datetime, timezone
from threading import RLock

from backend.agent_plan_execution import topological_order
from backend.llm.tool_execution import CANCELLED, FAILED, RUNNING, SUCCEEDED

from .models import LLMAgentCheckpoint

# A checkpoint is resumable only when it captured genuinely interrupted,
# unfinished progress: RUNNING (taken mid-flight, while a run was still
# going) or CANCELLED (stopped on request, not because anything failed).
# SUCCEEDED has nothing left to do; FAILED and REJECTED stopped for a
# reason resuming would silently paper over -- retrying either is
# autonomous replanning, out of scope here.
RESUMABLE_STATES = frozenset({RUNNING, CANCELLED})


class UnknownCheckpointError(KeyError):
    """Raised when latest()/resume() is given an execution_id with no saved checkpoint."""


class InvalidCheckpointError(ValueError):
    """Raised when resume() is asked to resume a checkpoint that cannot be resumed:
    its state is not in RESUMABLE_STATES, or its plan no longer passes
    Commit #2 validation."""


class LLMAgentCheckpointService:
    """Persists and resumes the progress of a Commit #4 plan execution.

    Not a second task/state framework: save() only *reads* Commit #4's own
    LLMAgentPlanExecution record and Commit #3's own LLMAgentStepExecution
    store and writes one immutable fact about them -- it holds no handler,
    calls no tool, and never invents progress that didn't already exist.
    resume() only *drives* the steps that checkpoint says are still
    pending, through Commit #3's execute_step() -- exactly what Commit #4
    itself would call, in the same dependency order (Commit #4's own
    topological_order, reused rather than re-derived), so authorization,
    idempotency, timeout, retry, and audit are still entirely whatever the
    existing tool-calling pipeline underneath Commit #3 enforces.

    A checkpoint never carries a step's result, only the step_id and the
    Commit #3 execution_id that already carries it -- "preserve tool
    execution IDs and results" means exactly that: a pointer to the one
    existing record, never a second copy of it. A step already listed as
    completed in the checkpoint being resumed is never handed to
    execute_step() again, whatever else has changed since.
    """

    def __init__(self, planning_service, validation_service, step_execution_service, plan_execution_service):
        self._planning_service = planning_service
        self._validation_service = validation_service
        self._step_execution_service = step_execution_service
        self._plan_execution_service = plan_execution_service
        self._checkpoints = {}
        self._latest_by_execution = {}
        self._counter = 0
        self._lock = RLock()

    def _current_progress(self, plan_id: str):
        """(completed-step pointers, current_step) as Commit #3 shows right now."""
        plan = self._planning_service.get(plan_id)
        succeeded_by_step_id = {
            record.step_id: record
            for record in self._step_execution_service.executions(plan_id)
            if record.status == SUCCEEDED
        }

        completed = []
        current_step = None
        for step in topological_order(plan.steps):
            record = succeeded_by_step_id.get(step.step_id)
            if record is None:
                current_step = step.step_id
                break
            completed.append({"step_id": step.step_id, "execution_id": record.execution_id})
        return completed, current_step

    def _record(self, execution_id, completed, current_step, state) -> LLMAgentCheckpoint:
        with self._lock:
            self._counter += 1
            checkpoint = LLMAgentCheckpoint(
                checkpoint_id=f"agent-checkpoint-{self._counter}",
                execution_id=execution_id,
                completed_steps=tuple(dict(entry) for entry in completed),
                current_step=current_step,
                state=state,
                created_at=datetime.now(timezone.utc),
            )
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            self._latest_by_execution[execution_id] = checkpoint.checkpoint_id
            return checkpoint

    def save(self, execution_id: str) -> LLMAgentCheckpoint:
        """Capture `execution_id`'s current, already-existing progress.

        Raises whatever backend.agent_plan_execution's own get() raises for
        an unrecorded execution_id -- this is not a second source of truth
        for what executions exist.
        """
        plan_execution = self._plan_execution_service.get(execution_id)
        completed, current_step = self._current_progress(plan_execution.plan_id)
        return self._record(execution_id, completed, current_step, plan_execution.status)

    @staticmethod
    def _copy(checkpoint: LLMAgentCheckpoint) -> LLMAgentCheckpoint:
        return LLMAgentCheckpoint(
            checkpoint_id=checkpoint.checkpoint_id,
            execution_id=checkpoint.execution_id,
            completed_steps=tuple(dict(entry) for entry in checkpoint.completed_steps),
            current_step=checkpoint.current_step,
            state=checkpoint.state,
            created_at=checkpoint.created_at,
        )

    def latest(self, execution_id: str) -> LLMAgentCheckpoint:
        """The most recently saved checkpoint for `execution_id`.

        Raises:
            UnknownCheckpointError: If none has ever been saved for it
        """
        with self._lock:
            checkpoint_id = self._latest_by_execution.get(execution_id)
            if checkpoint_id is None:
                raise UnknownCheckpointError(execution_id)
            return self._copy(self._checkpoints[checkpoint_id])

    def resume(self, execution_id: str, subject=None, timeout: float = None) -> LLMAgentCheckpoint:
        """Continue `execution_id` from its latest checkpoint, to completion or a stop.

        Every step the checkpoint already lists as completed is skipped
        outright -- never rerun, its existing Commit #3 record and result
        untouched. Each remaining step still runs through Commit #3's
        execute_step(), one at a time, in the plan's dependency order; the
        run stops the moment one does not SUCCEED, exactly as Commit #4's
        own execute() would, and a new checkpoint is saved recording
        wherever it ends up.

        Raises:
            UnknownCheckpointError: If execution_id has no saved checkpoint
            InvalidCheckpointError: If the latest checkpoint is not
                resumable, or the plan no longer passes Commit #2 validation
            ValueError: If steps remain but no subject was given to
                authorize them
        """
        checkpoint = self.latest(execution_id)
        if checkpoint.state not in RESUMABLE_STATES:
            raise InvalidCheckpointError(
                f"checkpoint {checkpoint.checkpoint_id!r} for execution {execution_id!r} is "
                f"{checkpoint.state}, not resumable"
            )

        plan_execution = self._plan_execution_service.get(execution_id)
        plan_id = plan_execution.plan_id

        if self._validation_service.blocking(plan_id):
            raise InvalidCheckpointError(
                f"plan {plan_id!r} no longer passes validation and cannot be resumed"
            )

        plan = self._planning_service.get(plan_id)
        completed = list(checkpoint.completed_steps)
        done_step_ids = {entry["step_id"] for entry in completed}

        for step in topological_order(plan.steps):
            if step.step_id in done_step_ids:
                continue  # never rerun a successfully completed step

            if subject is None:
                raise ValueError("subject is required to resume a plan with remaining steps")

            step_execution = self._step_execution_service.execute_step(
                plan_id, step.step_id, subject, timeout=timeout
            )
            if step_execution.status != SUCCEEDED:
                return self._record(execution_id, completed, step.step_id, FAILED)

            completed.append({"step_id": step.step_id, "execution_id": step_execution.execution_id})

        return self._record(execution_id, completed, None, SUCCEEDED)
