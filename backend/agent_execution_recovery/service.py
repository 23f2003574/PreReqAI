from backend.agent_checkpointing import RESUMABLE_STATES, InvalidCheckpointError
from backend.agent_plan_execution import topological_order
from backend.agent_step_execution import UnknownAgentStepExecutionError
from backend.llm.tool_execution import SUCCEEDED


class InconsistentCheckpointError(InvalidCheckpointError):
    """Raised when a checkpoint's completed_steps do not match Commit #3's own records.

    A subclass of Commit #5's own InvalidCheckpointError: a corrupted
    checkpoint is a kind of invalid one, so catching that one error still
    catches this. Raised when a claimed-complete step's execution_id no
    longer exists, belongs to a different step or plan, or was not
    actually SUCCEEDED -- any of which means the checkpoint cannot be
    trusted to describe what really happened.
    """


class LLMAgentRecoveryService:
    """Recovers an interrupted plan execution from its latest checkpoint, safely.

    Not a second recovery system: recover() adds exactly one thing Commit
    #5's own resume() does not do -- verifying every step a checkpoint
    claims is complete against Commit #3's own execution record before
    trusting it -- and then hands the actual continuation straight to
    Commit #5's resume(), unchanged. Nothing here runs a tool, retries a
    call, or authorizes anything; every one of those still belongs
    entirely to Commit #3's execute_step() and the existing tool-calling
    pipeline underneath it, exactly as Commit #5 already wires it.

    A checkpoint is trusted only as far as it can be verified:

        - its own state must be resumable (Commit #5's RESUMABLE_STATES)
        - every step it lists as completed must still have a real Commit
          #3 execution record, for the same step and the same plan, whose
          status is SUCCEEDED

    Anything else -- a missing execution, one that belongs to a different
    step, or one that did not actually succeed -- means the checkpoint is
    corrupted or inconsistent, and recovery refuses outright rather than
    silently skipping (and so never running) a step that was never really
    finished.
    """

    def __init__(
        self, planning_service, validation_service, step_execution_service,
        plan_execution_service, checkpoint_service,
    ):
        self._planning_service = planning_service
        self._validation_service = validation_service
        self._step_execution_service = step_execution_service
        self._plan_execution_service = plan_execution_service
        self._checkpoint_service = checkpoint_service

    def _verified_progress(self, execution_id: str):
        """The latest checkpoint, the plan, and the step_ids it genuinely completed.

        Raises:
            UnknownCheckpointError: If execution_id has no saved checkpoint
                (propagated from Commit #5, unchanged)
            InvalidCheckpointError: If the checkpoint's own state is not resumable
            InconsistentCheckpointError: If a claimed-complete step does not
                check out against Commit #3's own record
        """
        checkpoint = self._checkpoint_service.latest(execution_id)
        if checkpoint.state not in RESUMABLE_STATES:
            raise InvalidCheckpointError(
                f"checkpoint {checkpoint.checkpoint_id!r} for execution {execution_id!r} is "
                f"{checkpoint.state}, not resumable"
            )

        plan_execution = self._plan_execution_service.get(execution_id)
        plan = self._planning_service.get(plan_execution.plan_id)
        step_ids = {step.step_id for step in plan.steps}

        verified = []
        for entry in checkpoint.completed_steps:
            step_id, exec_id = entry["step_id"], entry["execution_id"]

            if step_id not in step_ids:
                raise InconsistentCheckpointError(
                    f"checkpoint claims step {step_id!r}, which is not part of "
                    f"plan {plan_execution.plan_id!r}"
                )

            try:
                record = self._step_execution_service.get(exec_id)
            except UnknownAgentStepExecutionError:
                raise InconsistentCheckpointError(
                    f"checkpoint's execution {exec_id!r} for step {step_id!r} no "
                    "longer has a Commit #3 record"
                )

            if record.plan_id != plan_execution.plan_id or record.step_id != step_id:
                raise InconsistentCheckpointError(
                    f"execution {exec_id!r} belongs to step {record.step_id!r} of plan "
                    f"{record.plan_id!r}, not step {step_id!r} of plan "
                    f"{plan_execution.plan_id!r} as the checkpoint claims"
                )

            if record.status != SUCCEEDED:
                raise InconsistentCheckpointError(
                    f"execution {exec_id!r} for step {step_id!r} is {record.status}, "
                    f"not {SUCCEEDED} -- the checkpoint cannot have completed it"
                )

            verified.append(step_id)

        return checkpoint, plan, verified

    def validate_checkpoint(self, execution_id: str) -> bool:
        """Whether execution_id's latest checkpoint may safely be recovered from.

        Never raises for an invalid or corrupted checkpoint -- only an
        unknown execution_id or checkpoint does, since there is then
        nothing at all to validate.
        """
        try:
            self._verified_progress(execution_id)
        except InvalidCheckpointError:
            return False
        return True

    def remaining_steps(self, execution_id: str) -> list:
        """step_ids not yet verified-complete, in dependency order.

        Exactly what recover() would still need to run -- read-only, and
        computed from Commit #3's own records, never from the checkpoint's
        unverified say-so.
        """
        _checkpoint, plan, verified = self._verified_progress(execution_id)
        verified_set = set(verified)
        return [step.step_id for step in topological_order(plan.steps) if step.step_id not in verified_set]

    def recover(self, execution_id: str, subject=None, timeout: float = None):
        """Resume execution_id from its latest checkpoint, once verified.

        The actual continuation -- skipping every verified-complete step
        and running the rest through Commit #3's execute_step(), in
        dependency order, stopping on the first that does not SUCCEED -- is
        entirely Commit #5's resume(), called unchanged; this method only
        decides whether that call is safe to make at all.

        Raises:
            UnknownCheckpointError: If execution_id has no saved checkpoint
            InvalidCheckpointError: If the checkpoint's state is not resumable
            InconsistentCheckpointError: If a claimed-complete step does not
                check out against Commit #3's own record
        """
        self._verified_progress(execution_id)
        return self._checkpoint_service.resume(execution_id, subject=subject, timeout=timeout)
