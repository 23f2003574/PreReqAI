from ..cost import LLMCostService, UnknownPricingError
from ..usage import LLMUsageService


class LLMCostAnalyticsService:
    """Aggregates spend from Commit #6's usage records and Commit #7's pricing.

    Reuses backend.llm.cost.LLMCostService.model_cost() for every rate --
    no second pricing registry, and the per-token formula it applies is
    exactly LLMCostService.estimate()'s own (tokens * rate). Estimate()
    itself scopes to one request_id and raises on any unpriced record or
    currency mix within it; this service aggregates across many records at
    once, so an unpriced record is tracked as explicitly unavailable
    instead of aborting everything else that could be priced.
    """

    def __init__(self, usage_service: LLMUsageService, cost_service: LLMCostService):
        self._usage_service = usage_service
        self._cost_service = cost_service

    def _price(self, record):
        """(currency, amount) for one usage record, or None if unpriced."""
        try:
            pricing = self._cost_service.model_cost(record.provider, record.model)
        except UnknownPricingError:
            return None

        amount = record.input_tokens * pricing.input_cost + record.output_tokens * pricing.output_cost
        return pricing.currency, amount

    def _summarize(self, records) -> dict:
        by_currency = {}
        priced_count = 0
        unpriced = set()

        for record in records:
            priced = self._price(record)
            if priced is None:
                unpriced.add((record.provider, record.model))
                continue

            currency, amount = priced
            by_currency[currency] = by_currency.get(currency, 0.0) + amount
            priced_count += 1

        return {
            "by_currency": {currency: round(amount, 6) for currency, amount in by_currency.items()},
            "count": priced_count,
            "unpriced_count": len(records) - priced_count,
            "unpriced": sorted(unpriced),
        }

    def total(self, scope: str = None) -> dict:
        """Cost summary for scope, or everything if omitted."""
        return self._summarize(self._usage_service.records(scope))

    def _group_by(self, scope, key) -> dict:
        groups = {}
        for record in self._usage_service.records(scope):
            groups.setdefault(key(record), []).append(record)
        return {group_key: self._summarize(records) for group_key, records in groups.items()}

    def by_provider(self, scope: str = None) -> dict:
        """Cost summaries grouped by provider, preserving provider identity."""
        return self._group_by(scope, key=lambda record: record.provider)

    def by_model(self, scope: str = None) -> dict:
        """Cost summaries grouped by model, preserving model identity."""
        return self._group_by(scope, key=lambda record: record.model)

    def by_period(self, scope: str, start, end) -> dict:
        """Cost summary for scope, narrowed to records recorded within [start, end]."""
        if start > end:
            raise ValueError("start must not be after end")

        matching = [
            record for record in self._usage_service.records(scope) if start <= record.recorded_at <= end
        ]
        return self._summarize(matching)
