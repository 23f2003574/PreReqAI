from datetime import datetime, timezone
from threading import RLock

from backend.llm.tool_control import ExecutionAlreadyCompletedError
from backend.llm.tool_execution import CANCELLED, FAILED, REJECTED, RUNNING, SUCCEEDED

from .models import LLMAgentPlanExecution


class PlanExecutionAlreadyExistsError(ValueError):
    """Raised when execute() is called for a plan_id that already has an execution.

    A plan is executed once here -- there is no autonomous re-planning or
    re-execution yet. Calling execute() again for the same plan_id, whether
    the first run is still going or has already finished, is refused
    outright rather than silently starting a second, independent run.
    """


class UnknownAgentPlanExecutionError(KeyError):
    """Raised when status()/steps()/cancel()/get() is given an unrecorded execution_id."""


def topological_order(steps: list) -> list:
    """steps ordered so every step follows all of its depends_on.

    Kahn's algorithm, picking the earliest-declared ready step at each tie
    so the order is deterministic and stays as close to the plan's own
    declared order as its dependencies allow. Assumes an acyclic graph --
    Commit #2 validation (checked by execute() before this is ever called)
    already refuses a plan with a dependency cycle, so this never has to
    detect one itself.

    Module-level so that Commit #5's checkpointing walks the same
    dependency order this service does, rather than keeping a second copy
    of it in step.
    """
    remaining = list(steps)
    indegree = {step.step_id: len(step.depends_on) for step in steps}
    order = []

    while remaining:
        ready = next((step for step in remaining if indegree[step.step_id] == 0), None)
        if ready is None:
            break  # pragma: no cover -- unreachable for a plan that passed validation
        order.append(ready)
        remaining.remove(ready)
        for step in remaining:
            if ready.step_id in step.depends_on:
                indegree[step.step_id] -= 1

    return order


class LLMAgentPlanExecutionService:
    """Executes an entire Commit #1 plan, one Commit #3 step at a time.

    This is not a second execution engine: every step is run by handing it
    to Commit #3's own LLMAgentExecutionService.execute_step(), unchanged --
    which is itself only a thin layer over the existing
    backend.llm.tool_orchestration pipeline. This service adds exactly one
    thing neither of those has any notion of: an order to run several
    steps in, and when to stop early.

    Reused rather than re-implemented at every step:

        Commit #1 planning_service    -- the plan and its steps
        Commit #2 validation_service  -- "may this plan run at all"
        Commit #3 step_execution      -- runs one step, through the real
                                          tool-calling pipeline (Commit #4's
                                          authorization, idempotency,
                                          timeout, retry, and audit,
                                          whichever the caller wired it with)

    execute() computes a dependency-respecting order for the plan's steps
    and runs them one at a time, in the calling thread, stopping the
    moment a step's own execution does not SUCCEED -- a step is never
    started until every step it depends on has already succeeded, exactly
    as Commit #3 additionally re-checks per step. Nothing here retries a
    failed step, works around a denial, or re-plans; a blocking failure
    simply ends the run, leaving completed_steps as the honest record of
    how far it got.

    Cancellation is cooperative, for the same reason Commit #10's own
    control service documents: Python has no way to stop a thread that is
    genuinely still inside a tool call. cancel() only ever flags the run;
    the currently in-flight step finishes on its own (bounded by whatever
    timeout the caller passed through), and the loop notices the flag and
    stops *before starting the next step* -- so a cancelled run's own
    record is always an honest, safely-stopped prefix of the plan, never a
    step interrupted midway and reported as anything but what it actually
    did.
    """

    def __init__(self, planning_service, validation_service, step_execution_service):
        self._planning_service = planning_service
        self._validation_service = validation_service
        self._step_execution_service = step_execution_service
        self._executions = {}
        self._by_plan = {}
        self._cancel_requested = {}
        self._counter = 0
        self._lock = RLock()

    def _store(self, execution: LLMAgentPlanExecution) -> LLMAgentPlanExecution:
        with self._lock:
            self._executions[execution.execution_id] = execution
            return execution

    def execute(self, plan_id: str, subject, timeout: float = None) -> LLMAgentPlanExecution:
        """Run every step of `plan_id`, in dependency order, on behalf of `subject`.

        Never raises for a rejected, failed, or cancelled run -- every
        attempt becomes an LLMAgentPlanExecution whose status says what
        happened. Only a caller error (an unknown plan_id, or a repeat
        execute() for a plan already executed) raises.
        """
        with self._lock:
            if plan_id in self._by_plan:
                raise PlanExecutionAlreadyExistsError(
                    f"plan {plan_id!r} has already been executed"
                )

            plan = self._planning_service.get(plan_id)

            self._counter += 1
            execution_id = f"agent-plan-execution-{self._counter}"
            started_at = datetime.now(timezone.utc)
            self._by_plan[plan_id] = execution_id
            self._cancel_requested[execution_id] = False
            self._store(
                LLMAgentPlanExecution(
                    execution_id=execution_id, plan_id=plan_id, status=RUNNING,
                    completed_steps=[], failed_step=None,
                    started_at=started_at, completed_at=None,
                )
            )

        # 1. The plan as a whole must pass Commit #2 validation before any
        #    step ever runs -- checked here, once, so a rejected plan never
        #    creates a single Commit #3 step-execution record.
        if self._validation_service.blocking(plan_id):
            return self._finish(execution_id, plan_id, REJECTED, [], None, started_at)

        completed_steps = []
        for step in topological_order(plan.steps):
            with self._lock:
                if self._cancel_requested[execution_id]:
                    return self._finish(
                        execution_id, plan_id, CANCELLED, completed_steps, None, started_at
                    )

            # 2. Run only this step, entirely through Commit #3 -- dependency
            #    success, authorization, execution, and everything under it
            #    is that service's own concern, not re-checked or
            #    re-implemented here.
            step_execution = self._step_execution_service.execute_step(
                plan_id, step.step_id, subject, timeout=timeout
            )

            if step_execution.status != SUCCEEDED:
                return self._finish(
                    execution_id, plan_id, FAILED, completed_steps, step.step_id, started_at
                )

            completed_steps.append(step.step_id)

        return self._finish(execution_id, plan_id, SUCCEEDED, completed_steps, None, started_at)

    def _finish(
        self, execution_id, plan_id, status, completed_steps, failed_step, started_at
    ) -> LLMAgentPlanExecution:
        return self._store(
            LLMAgentPlanExecution(
                execution_id=execution_id, plan_id=plan_id, status=status,
                completed_steps=list(completed_steps), failed_step=failed_step,
                started_at=started_at, completed_at=datetime.now(timezone.utc),
            )
        )

    def _get(self, execution_id: str) -> LLMAgentPlanExecution:
        with self._lock:
            try:
                return self._executions[execution_id]
            except KeyError:
                raise UnknownAgentPlanExecutionError(execution_id)

    def get(self, execution_id: str) -> LLMAgentPlanExecution:
        return self._get(execution_id)

    def status(self, execution_id: str) -> str:
        return self._get(execution_id).status

    def steps(self, execution_id: str) -> list:
        """Every Commit #3 LLMAgentStepExecution recorded so far for this run.

        Reads straight through to Commit #3's own store, in the order those
        records were created -- which is execution order. Nothing here
        keeps a second copy of a step's outcome.
        """
        execution = self._get(execution_id)
        return self._step_execution_service.executions(plan_id=execution.plan_id)

    def cancel(self, execution_id: str) -> LLMAgentPlanExecution:
        """Request that a running plan execution stop before its next step.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never recorded
            ExecutionAlreadyCompletedError: If it is not currently RUNNING --
                the same error Commit #10's own control service raises for
                exactly this situation, reused rather than redefined
        """
        with self._lock:
            execution = self._get(execution_id)
            if execution.status != RUNNING:
                raise ExecutionAlreadyCompletedError(
                    f"Cannot cancel execution {execution_id!r}: it is already "
                    f"{execution.status}."
                )
            self._cancel_requested[execution_id] = True
            return execution
