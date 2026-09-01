from datetime import datetime, timezone

from backend.llm.tool_execution import REJECTED, SUCCEEDED

from .models import LLMAgentStepExecution


class UnknownAgentStepError(KeyError):
    """Raised when execute_step() is given a step_id that isn't part of the plan."""


class UnknownAgentStepExecutionError(KeyError):
    """Raised when status()/result()/get() is given an unrecorded execution_id."""


class StepNotSucceededError(ValueError):
    """Raised when result() is called for an execution that did not succeed.

    Mirrors backend.llm.tool_execution.ExecutionNotSucceededError one level
    up: a step that was rejected, denied, failed, or timed out has no
    result, and returning None for one would let a caller mistake "it did
    not run" for "it ran and returned nothing".
    """


class LLMAgentExecutionService:
    """Executes one step of a Commit #1 LLMAgentPlan, on request, one at a time.

    This is not a second execution engine: every gate that decides whether
    a tool call may actually run -- registry existence, schema validation,
    Commit #4 authorization, idempotency, a timeout deadline, retry -- is
    entirely the existing backend.llm.tool_orchestration.
    LLMToolCallingOrchestrationService's, wired however the caller already
    wires it. This service only adds the two checks that pipeline has no
    way to know about, because it has never heard of an agent plan:

        1. the plan as a whole must currently pass Commit #2 validation
        2. every dependency this step lists must have already been
           executed, by this same service, and have SUCCEEDED

    Both refuse the step as REJECTED, before the tool-calling pipeline is
    ever entered -- so a plan that cannot run, or a step whose
    prerequisite failed, never reaches authorization or a handler at all.
    Every other outcome (SUCCEEDED, FAILED, DENIED, TIMED_OUT, CANCELLED)
    is the orchestrator's own decision, copied here verbatim: this service
    never re-derives, downgrades, or upgrades what actually happened.

    execute_step() runs exactly the one step named -- it never walks
    depends_on to run anything else, and never touches any other step of
    the plan. Running a whole plan end to end is a later commit's job.
    """

    def __init__(self, planning_service, validation_service, tool_orchestration_service):
        self._planning_service = planning_service
        self._validation_service = validation_service
        self._tool_orchestration_service = tool_orchestration_service
        self._executions = {}
        self._latest_by_plan_step = {}
        self._counter = 0

    @staticmethod
    def _find_step(plan, step_id: str):
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        raise UnknownAgentStepError(f"plan {plan.plan_id!r} has no step {step_id!r}")

    def _record(
        self, plan_id: str, step_id: str, status: str, result, error, started_at
    ) -> LLMAgentStepExecution:
        self._counter += 1
        execution = LLMAgentStepExecution(
            execution_id=f"agent-step-execution-{self._counter}",
            plan_id=plan_id,
            step_id=step_id,
            status=status,
            result=result,
            error=error,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
        self._executions[execution.execution_id] = execution
        self._latest_by_plan_step[(plan_id, step_id)] = execution
        return execution

    def _dependency_error(self, plan_id: str, step) -> str:
        """Why this step's dependencies block it from running, or None."""
        for dependency_id in step.depends_on:
            dependency_execution = self._latest_by_plan_step.get((plan_id, dependency_id))
            if dependency_execution is None:
                return f"dependency step {dependency_id!r} has not been executed yet"
            if dependency_execution.status != SUCCEEDED:
                return (
                    f"dependency step {dependency_id!r} did not succeed "
                    f"(status {dependency_execution.status})"
                )
        return None

    def execute_step(
        self, plan_id: str, step_id: str, subject, timeout: float = None
    ) -> LLMAgentStepExecution:
        """Run exactly one step of `plan_id` on behalf of `subject`.

        Never raises for a refused or failing call -- every attempt becomes
        an LLMAgentStepExecution whose status says what happened. Only a
        caller error (an unknown plan_id or step_id) raises, propagated
        from Commit #1's own planning_service.get().
        """
        plan = self._planning_service.get(plan_id)
        step = self._find_step(plan, step_id)

        started_at = datetime.now(timezone.utc)

        # 1. The plan as a whole must pass Commit #2 validation. Re-checked
        #    here rather than trusted from whenever the plan was created or
        #    last validated -- a tool or policy can change in between.
        if self._validation_service.blocking(plan_id):
            findings = self._validation_service.validate(plan_id)
            summary = "; ".join(
                f"{finding.step_id}: {finding.message}" for finding in findings if finding.blocking
            )
            return self._record(
                plan_id, step_id, REJECTED, None,
                f"plan {plan_id!r} failed validation: {summary}", started_at,
            )

        # 2. Every dependency must already have succeeded, per this
        #    service's own record of prior executions -- not the plan's
        #    static depends_on shape, which Commit #2 already checked.
        dependency_error = self._dependency_error(plan_id, step)
        if dependency_error is not None:
            return self._record(plan_id, step_id, REJECTED, None, dependency_error, started_at)

        # 3. Execute only this step, entirely through the existing
        #    tool-calling pipeline. Authorization, idempotency, a timeout
        #    deadline, retry, and audit are whichever of those the
        #    orchestrator was wired with -- nothing here re-implements any
        #    of them.
        tool_call = {"name": step.tool_name, "arguments": dict(step.arguments)}
        request_id = f"agent-step-{plan_id}-{step_id}-{self._counter + 1}"
        decision = self._tool_orchestration_service.execute(
            tool_call, subject, request_id=request_id, timeout=timeout
        )

        result = decision.result if decision.status == SUCCEEDED else None
        error = None if decision.status == SUCCEEDED else decision.reason

        return self._record(plan_id, step_id, decision.status, result, error, started_at)

    def _get(self, execution_id: str) -> LLMAgentStepExecution:
        try:
            return self._executions[execution_id]
        except KeyError:
            raise UnknownAgentStepExecutionError(execution_id)

    def get(self, execution_id: str) -> LLMAgentStepExecution:
        return self._get(execution_id)

    def status(self, execution_id: str) -> str:
        return self._get(execution_id).status

    def result(self, execution_id: str):
        """The normalized result the step's tool returned.

        Raises:
            UnknownAgentStepExecutionError: If execution_id was never recorded
            StepNotSucceededError: If that execution did not succeed
        """
        execution = self._get(execution_id)
        if execution.status != SUCCEEDED:
            raise StepNotSucceededError(
                f"execution {execution_id!r} is {execution.status}, not {SUCCEEDED}: "
                f"{execution.error}"
            )
        return execution.result

    def executions(self, plan_id: str = None) -> list:
        recorded = list(self._executions.values())
        if plan_id is not None:
            recorded = [execution for execution in recorded if execution.plan_id == plan_id]
        return recorded
