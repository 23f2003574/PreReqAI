from datetime import datetime, timezone

from backend.agent_step_execution import LLMAgentExecutionService
from backend.llm.tool_execution import DENIED

from .enforcement import LLMAgentPolicyEnforcement, PolicyEvaluationFailedError, is_blocking


class LLMAgentPolicyEnforcedExecutionService(LLMAgentExecutionService):
    """backend.agent_step_execution.LLMAgentExecutionService, unchanged,
    with exactly one more pre-execution gate: Commit #1-#4 policy
    enforcement.

    Not a second execution pipeline: this subclasses the real
    LLMAgentExecutionService rather than reimplementing or wrapping its
    behavior at arm's length, so every existing gate (Commit #2 plan
    validation, dependency completion, and the whole
    backend.llm.tool_orchestration pipeline underneath) still runs
    exactly as before -- execute_step() here only adds a check *before*
    any of that, in the same "gate, then delegate" shape the base class
    already uses for its own two gates. When enforcement allows the
    action, this method's own logic ends there and
    super().execute_step() carries out the rest completely unchanged,
    so "existing behavior remains unchanged when no applicable policy
    blocks it" holds by construction, not by re-deriving what the base
    class already does correctly.

    A blocked action -- see is_blocking() -- is recorded via the base
    class's own private _record() (accessible here as an ordinary
    inherited method, not reimplemented) exactly the way the base class
    already records a tool-permission denial: as an LLMAgentStepExecution
    with status DENIED -- reusing backend.llm.tool_execution's own
    vocabulary rather than inventing a second one -- and is never handed
    to tool_orchestration_service at all, so a denied action can never
    reach real execution. A PolicyEvaluationFailedError from enforce()
    is recorded the same way: fail closed, never let evaluation trouble
    look like permission to proceed. Both preserve the base class's own
    documented contract ("never raises for a refused or failing call")
    exactly, which backend.agent_plan_execution.LLMAgentPlanExecutionService
    already depends on when it branches on a step's .status; raising
    here instead would silently break that caller.

    scope_for_plan is a plain callable, plan_id -> scope_id, supplied by
    the caller, the same integration-seam shape Commit #2's
    LLMAgentPolicyResolver.resolve_for_execution() already uses for
    scope_for_execution -- there is no existing plan-to-scope index
    anywhere in this repository (an LLMAgentPlan carries no scope_id at
    all) for the same reason execution_id has none either.
    """

    def __init__(
        self,
        planning_service,
        validation_service,
        tool_orchestration_service,
        enforcement: LLMAgentPolicyEnforcement,
        scope_for_plan,
    ):
        super().__init__(planning_service, validation_service, tool_orchestration_service)
        self._enforcement = enforcement
        self._scope_for_plan = scope_for_plan

    def execute_step(self, plan_id: str, step_id: str, subject, timeout: float = None):
        """Run exactly one step of `plan_id`, as
        LLMAgentExecutionService.execute_step() already does, after first
        checking it against every policy applicable to this plan's scope.

        Never raises for a refused, denied, or failing call, exactly like
        the base class -- only an unknown plan_id or step_id raises,
        propagated from the base class's own planning_service.get()/
        _find_step().
        """
        plan = self._planning_service.get(plan_id)
        step = self._find_step(plan, step_id)
        started_at = datetime.now(timezone.utc)

        action_context = {
            "scope_id": self._scope_for_plan(plan_id),
            "plan_id": plan_id,
            "step_id": step_id,
            "tool_name": step.tool_name,
            "arguments": dict(step.arguments),
            "subject": subject,
        }

        try:
            decision = self._enforcement.enforce(action_context)
        except PolicyEvaluationFailedError as error:
            return self._record(
                plan_id, step_id, DENIED, None,
                f"blocked by agent policy: evaluation failed and fails closed ({error})",
                started_at,
            )

        if is_blocking(decision):
            reason = "; ".join(decision.reasons) or "denied by agent policy"
            return self._record(
                plan_id, step_id, DENIED, None, f"blocked by agent policy: {reason}", started_at
            )

        return super().execute_step(plan_id, step_id, subject, timeout=timeout)
