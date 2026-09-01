from threading import RLock

from backend.llm.budget import BudgetExceededError, LLMBudgetService

BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
WITHIN_BUDGET = "WITHIN_BUDGET"
STATES = frozenset({BUDGET_EXCEEDED, WITHIN_BUDGET})

_DIMENSIONS = ("steps", "tokens", "cost", "duration")
_LIMIT_KEYS = {"steps": "max_steps", "tokens": "max_tokens", "cost": "max_cost", "duration": "max_duration"}


class UnknownExecutionBudgetError(KeyError):
    """Raised when check()/consume()/remaining()/exceeded() names an
    execution_id that was never configure()d."""


class InvalidUsageError(ValueError):
    """Raised when consume() is given a negative usage amount."""


class LLMAgentExecutionBudgetService:
    """Bounds one plan execution's steps, tokens, cost, and duration.

    Not a second budget framework: token and cost accumulation is entirely
    the existing backend.llm.budget.LLMBudgetService's own bookkeeping, one
    scope per execution_id -- reused rather than re-implemented -- but
    configured here with no max of its own, so its consume() never raises.
    That is deliberate: a step that already ran must always have its real
    usage recorded, even if doing so crosses a limit, the same way
    LLMRequestOrchestrationService already records a request's usage after
    the fact rather than refusing to acknowledge it happened. This service
    is what then refuses to let a *further* step start, never what
    un-spends what a finished one already spent. steps and duration have
    no existing repository-wide limiter to reuse, so they are tracked the
    same way LLMBudgetService itself tracks tokens and cost: a small,
    per-execution running total, incremented only by consume(), and never
    derived from anything else.

    check() is what "enforce limits before starting the next step" means
    in practice: call it before asking Commit #3 to run the next step: it
    raises backend.llm.budget's own BudgetExceededError -- not a second
    exception type -- the moment any configured limit has already been
    reached (steps) or passed (tokens, cost, duration). Nothing here ever
    calls execute_step(), authorizes anything, or otherwise touches the
    tool-calling pipeline: a budget decision can only ever refuse to ask
    for the next step, never substitute for, or bypass, that step's own
    authorization.

    steps uses "at the limit already" (>=) as exceeded, since it is an
    exact count of whole steps -- max_steps=2 means at most 2 ever run.
    tokens, cost, and duration use "strictly past the limit" (>), the same
    convention LLMBudgetService itself uses, since those are measured
    after the fact and cannot be sized in advance.
    """

    def __init__(self, budget_service: LLMBudgetService = None):
        self._budget_service = budget_service or LLMBudgetService()
        self._limits = {}
        self._usage = {}
        self._lock = RLock()

    def configure(
        self, execution_id: str, max_steps: int = None, max_tokens: int = None,
        max_cost: float = None, max_duration: float = None,
    ) -> dict:
        """Set (or update) execution_id's limits. Safe to call again for the
        same execution_id -- as LLMBudgetService.configure() already does,
        this only ever changes the limits, never the usage accumulated so
        far, so re-configuring (say, after a Commit #6 recovery) never
        resets what has already been consumed."""
        with self._lock:
            self._limits[execution_id] = {
                "max_steps": max_steps, "max_tokens": max_tokens,
                "max_cost": max_cost, "max_duration": max_duration,
            }
            self._usage.setdefault(execution_id, {"steps": 0, "duration": 0.0})
            # Idempotent: LLMBudgetService.configure() updates only the
            # limits (None, i.e. unlimited, here) on an existing scope and
            # leaves its used_tokens/used_cost untouched.
            self._budget_service.configure(execution_id, max_tokens=None, max_cost=None)
        return self._snapshot(execution_id)

    def _limit(self, execution_id: str) -> dict:
        with self._lock:
            try:
                return self._limits[execution_id]
            except KeyError:
                raise UnknownExecutionBudgetError(execution_id)

    def _usage_snapshot(self, execution_id: str):
        limits = self._limit(execution_id)
        token_cost_budget = self._budget_service.get(execution_id)
        with self._lock:
            local = self._usage[execution_id]
            usage = {
                "steps": local["steps"],
                "duration": local["duration"],
                "tokens": token_cost_budget.used_tokens,
                "cost": token_cost_budget.used_cost,
            }
        return usage, limits

    def _violations(self, execution_id: str):
        usage, limits = self._usage_snapshot(execution_id)
        violations = []
        for dimension in _DIMENSIONS:
            limit = limits[_LIMIT_KEYS[dimension]]
            if limit is None:
                continue
            over = usage[dimension] >= limit if dimension == "steps" else usage[dimension] > limit
            if over:
                violations.append(dimension)
        return violations, usage, limits

    def check(self, execution_id: str) -> bool:
        """Whether the next step may start. Raises if it may not.

        Raises:
            UnknownExecutionBudgetError: If execution_id was never configured
            BudgetExceededError: If any configured limit is already reached
                or passed
        """
        violations, usage, limits = self._violations(execution_id)
        if violations:
            raise BudgetExceededError(
                f"execution {execution_id!r} has exceeded its budget on: "
                f"{', '.join(violations)} (usage={usage}, limits={limits})"
            )
        return True

    def consume(self, execution_id: str, usage: dict) -> dict:
        """Record usage a step already incurred. Never raises for exceeding
        a limit -- the work already happened; check() is what refuses the
        next one."""
        self._limit(execution_id)  # validates existence

        steps = usage.get("steps", 0)
        tokens = usage.get("tokens", 0)
        cost = usage.get("cost", 0.0)
        duration = usage.get("duration", 0.0)

        if steps < 0 or tokens < 0 or cost < 0 or duration < 0:
            raise InvalidUsageError("usage values must not be negative")

        with self._lock:
            self._usage[execution_id]["steps"] += steps
            self._usage[execution_id]["duration"] += duration

        # Configured above with no max of its own, so this never raises.
        self._budget_service.consume(execution_id, tokens=tokens, cost=cost)
        return self._snapshot(execution_id)

    def consume_step(self, execution_id: str, step_execution, tokens: int = 0, cost: float = 0.0) -> dict:
        """Convenience: derive steps/duration from a real Commit #3
        LLMAgentStepExecution record rather than a caller recomputing them.
        tokens/cost have no automatic source -- a tool call carries no
        universal cost model -- so default to what the step's own
        normalized SUCCEEDED result already estimated, or 0.
        """
        duration = (step_execution.completed_at - step_execution.started_at).total_seconds()
        if not tokens and step_execution.result is not None:
            tokens = step_execution.result.metadata.get("estimated_tokens", 0)
        return self.consume(
            execution_id, {"steps": 1, "tokens": tokens, "cost": cost, "duration": duration}
        )

    def remaining(self, execution_id: str) -> dict:
        usage, limits = self._usage_snapshot(execution_id)
        return {
            dimension: (
                None if limits[_LIMIT_KEYS[dimension]] is None
                else max(limits[_LIMIT_KEYS[dimension]] - usage[dimension], 0)
            )
            for dimension in _DIMENSIONS
        }

    def exceeded(self, execution_id: str) -> str:
        violations, _usage, _limits = self._violations(execution_id)
        return BUDGET_EXCEEDED if violations else WITHIN_BUDGET

    def _snapshot(self, execution_id: str) -> dict:
        usage, limits = self._usage_snapshot(execution_id)
        return {"usage": usage, "limits": limits}
