from backend.agent_execution_budget import UnknownExecutionBudgetError
from backend.llm.budget import BudgetExceededError
from backend.llm.tool_execution import RUNNING


class LLMAgentSchedulerService:
    """Decides which of a plan execution's steps may be dispatched right now.

    Not a second scheduler or workflow engine: readiness is entirely
    Commit #8's own LLMAgentDependencyService.ready_steps() -- the same
    dependency-safe, plan-order-preserving classification, never
    re-derived here -- and budget gating is entirely Commit #10's own
    LLMAgentExecutionBudgetService.check(). This service adds only the
    one thing neither of those already knows about: whether the plan
    execution as a whole (Commit #4, when wired) has been cancelled or
    otherwise stopped, since a step Commit #8 would still call "ready" (no
    attempt recorded, dependencies satisfied) must never be handed out
    once the run it belongs to is no longer RUNNING.

    schedule() never calls execute_step(), authorizes anything, or
    otherwise touches the tool-calling pipeline -- it only reads. A step
    it returns still goes through Commit #3's full authorization,
    idempotency, timeout, and retry the moment a caller actually runs it;
    this service cannot bypass any of that because it never runs anything
    at all.

    ready() and schedule() can both return more than one step_id at once
    -- the plan-order-preserving list of everything currently
    dependency-ready (ready()) or currently dispatchable (schedule()),
    covering the parallel-ready case where several independent steps have
    no unmet dependency at the same time. next_step() is the convenience
    for a caller that only wants one: the first entry schedule() would
    return, or None.
    """

    def __init__(self, dependency_service, budget_service=None, plan_execution_service=None):
        self._dependency_service = dependency_service
        self._budget_service = budget_service
        self._plan_execution_service = plan_execution_service

    def _plan_execution_stopped(self, execution_id: str) -> bool:
        """True only when a Commit #4 record for execution_id exists and
        says it is no longer RUNNING (cancelled, succeeded, failed, or
        rejected) -- nothing left, or safe, to schedule. Unknown to Commit
        #4 at all (no plan_execution_service wired, or no record yet, as
        when steps are driven directly through Commit #3) is not treated
        as stopped: there is simply no cancellation state to consult."""
        if self._plan_execution_service is None:
            return False
        try:
            plan_execution = self._plan_execution_service.get(execution_id)
        except Exception:
            return False
        return plan_execution.status != RUNNING

    def _within_budget(self, execution_id: str) -> bool:
        """True when no budget is configured for execution_id at all (an
        unconfigured execution is unbounded), or Commit #10 confirms it has
        not yet been exceeded."""
        if self._budget_service is None:
            return True
        try:
            self._budget_service.check(execution_id)
        except UnknownExecutionBudgetError:
            return True
        except BudgetExceededError:
            return False
        return True

    def ready(self, execution_id: str) -> list:
        """Every dependency-ready step_id, in Commit #8's own deterministic
        plan order. Ignores budget and cancellation -- the raw readiness
        view, not what may actually be dispatched right now."""
        return self._dependency_service.ready_steps(execution_id)

    def schedule(self, execution_id: str) -> list:
        """Every step_id that may actually be dispatched right now.

        Empty whenever the plan execution is no longer running, or its
        budget has already been exceeded -- in either case regardless of
        what ready() alone would say. Never executes anything and never
        mutates any state; safe to call repeatedly.
        """
        if self._plan_execution_stopped(execution_id):
            return []
        if not self._within_budget(execution_id):
            return []
        return self.ready(execution_id)

    def next_step(self, execution_id: str):
        """The single step schedule() would hand out first, or None."""
        scheduled = self.schedule(execution_id)
        return scheduled[0] if scheduled else None
