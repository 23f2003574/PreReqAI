from .models import LLMRequestBudget


class InvalidBudgetError(ValueError):
    """Raised when configure() is called with invalid limits."""


class UnknownBudgetError(KeyError):
    """Raised when looking up a scope_id that has not been configured."""


class BudgetExceededError(Exception):
    """Raised when a request would exceed, or has exceeded, a scope's budget."""


class LLMBudgetService:
    """Enforces configurable token/cost limits before LLM requests execute.

    Callers typically derive `estimated_tokens`/`estimated_cost` for check(),
    and `tokens`/`cost` for consume(), from Commit #6's LLMUsageService and
    Commit #7's LLMCostService -- e.g. usage_record.total_tokens and
    cost_estimate.total_cost -- rather than computing them independently here.
    """

    def __init__(self):
        self._budgets = {}
        self._counter = 0

    def configure(
        self, scope_id, max_tokens=None, max_cost=None, enabled=True
    ) -> LLMRequestBudget:
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidBudgetError("scope_id is required")

        if max_tokens is not None and max_tokens < 0:
            raise InvalidBudgetError("max_tokens must not be negative")

        if max_cost is not None and max_cost < 0:
            raise InvalidBudgetError("max_cost must not be negative")

        budget = self._budgets.get(scope_id)
        if budget is None:
            self._counter += 1
            budget = LLMRequestBudget(
                budget_id=f"budget-{self._counter}",
                scope_id=scope_id,
                max_tokens=max_tokens,
                max_cost=max_cost,
                used_tokens=0,
                used_cost=0.0,
                enabled=enabled,
            )
            self._budgets[scope_id] = budget
        else:
            budget.max_tokens = max_tokens
            budget.max_cost = max_cost
            budget.enabled = enabled

        return budget

    def get(self, scope_id) -> LLMRequestBudget:
        """Read-only fetch of scope_id's current budget state."""
        return self._get(scope_id)

    def _get(self, scope_id) -> LLMRequestBudget:
        try:
            return self._budgets[scope_id]
        except KeyError:
            raise UnknownBudgetError(scope_id)

    def check(self, scope_id, estimated_tokens=0, estimated_cost=0.0) -> bool:
        budget = self._get(scope_id)
        if not budget.enabled:
            return True

        if (
            budget.max_tokens is not None
            and budget.used_tokens + estimated_tokens > budget.max_tokens
        ):
            raise BudgetExceededError(
                f"scope {scope_id!r} would exceed token budget: "
                f"{budget.used_tokens} + {estimated_tokens} > {budget.max_tokens}"
            )

        if (
            budget.max_cost is not None
            and budget.used_cost + estimated_cost > budget.max_cost
        ):
            raise BudgetExceededError(
                f"scope {scope_id!r} would exceed cost budget: "
                f"{budget.used_cost} + {estimated_cost} > {budget.max_cost}"
            )

        return True

    def consume(self, scope_id, tokens=0, cost=0.0) -> LLMRequestBudget:
        budget = self._get(scope_id)

        if tokens < 0 or cost < 0:
            raise InvalidBudgetError("tokens/cost must not be negative")

        if budget.enabled:
            if (
                budget.max_tokens is not None
                and budget.used_tokens + tokens > budget.max_tokens
            ):
                raise BudgetExceededError(
                    f"scope {scope_id!r} cannot consume {tokens} tokens: "
                    f"{budget.used_tokens} + {tokens} > {budget.max_tokens}"
                )

            if (
                budget.max_cost is not None
                and budget.used_cost + cost > budget.max_cost
            ):
                raise BudgetExceededError(
                    f"scope {scope_id!r} cannot consume cost {cost}: "
                    f"{budget.used_cost} + {cost} > {budget.max_cost}"
                )

        budget.used_tokens += tokens
        budget.used_cost += cost
        return budget

    def remaining(self, scope_id) -> dict:
        budget = self._get(scope_id)

        tokens_remaining = (
            None
            if budget.max_tokens is None
            else max(budget.max_tokens - budget.used_tokens, 0)
        )
        cost_remaining = (
            None
            if budget.max_cost is None
            else max(budget.max_cost - budget.used_cost, 0.0)
        )
        return {"tokens": tokens_remaining, "cost": cost_remaining}

    def reset(self, scope_id) -> LLMRequestBudget:
        budget = self._get(scope_id)
        budget.used_tokens = 0
        budget.used_cost = 0.0
        return budget
