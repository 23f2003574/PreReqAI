from ..budget import LLMBudgetService
from ..cost_analytics import LLMCostAnalyticsService
from ..usage_aggregation import LLMUsageAggregationService


def _utilization(used, limit):
    """used/limit as a fraction, tolerant of a zero limit; None means no limit configured."""
    if limit is None:
        return None
    if limit == 0:
        return 0.0 if used == 0 else float("inf")
    return round(used / limit, 6)


class LLMBudgetAnalyticsService:
    """Reports consumption against Commit #8's configured budgets -- no second budget system.

    Reuses backend.llm.budget.LLMBudgetService for the configured limits and
    the actual used_tokens/used_cost it already accumulates via consume()
    (itself fed from Commit #6/#7's usage and cost calculations, per that
    service's own convention) -- nothing here recomputes consumption
    independently. by_provider()/by_model() additionally reuse Commit #9's
    LLMUsageAggregationService and Commit #10's LLMCostAnalyticsService for
    the identity breakdown, passing scope straight through to them.
    """

    def __init__(
        self,
        budget_service: LLMBudgetService,
        usage_analytics: LLMUsageAggregationService,
        cost_analytics: LLMCostAnalyticsService,
    ):
        self._budget_service = budget_service
        self._usage_analytics = usage_analytics
        self._cost_analytics = cost_analytics

    def usage(self, scope: str) -> dict:
        """Token consumption for scope: what was used, and the configured limit."""
        budget = self._budget_service.get(scope)
        return {"used_tokens": budget.used_tokens, "max_tokens": budget.max_tokens}

    def cost(self, scope: str) -> dict:
        """Cost consumption for scope: what was used, and the configured limit."""
        budget = self._budget_service.get(scope)
        return {"used_cost": budget.used_cost, "max_cost": budget.max_cost}

    def remaining(self, scope: str) -> dict:
        """Remaining tokens/cost for scope -- negative, never clamped, when over budget."""
        budget = self._budget_service.get(scope)

        tokens_remaining = (
            None if budget.max_tokens is None else budget.max_tokens - budget.used_tokens
        )
        cost_remaining = None if budget.max_cost is None else budget.max_cost - budget.used_cost

        return {
            "tokens": tokens_remaining,
            "cost": cost_remaining,
            "over_budget_tokens": tokens_remaining is not None and tokens_remaining < 0,
            "over_budget_cost": cost_remaining is not None and cost_remaining < 0,
        }

    def utilization(self, scope: str) -> dict:
        """Fraction of each configured limit consumed -- can exceed 1.0 when over budget."""
        budget = self._budget_service.get(scope)

        tokens_utilization = _utilization(budget.used_tokens, budget.max_tokens)
        cost_utilization = _utilization(budget.used_cost, budget.max_cost)

        return {
            "tokens": tokens_utilization,
            "cost": cost_utilization,
            "over_budget": (tokens_utilization is not None and tokens_utilization > 1.0)
            or (cost_utilization is not None and cost_utilization > 1.0),
        }

    def by_provider(self, scope: str = None) -> dict:
        """Usage/cost breakdown by provider, reusing Commit #9/#10's own grouping."""
        return {
            "usage": self._usage_analytics.by_provider(scope),
            "cost": self._cost_analytics.by_provider(scope),
        }

    def by_model(self, scope: str = None) -> dict:
        """Usage/cost breakdown by model, reusing Commit #9/#10's own grouping."""
        return {
            "usage": self._usage_analytics.by_model(scope),
            "cost": self._cost_analytics.by_model(scope),
        }
