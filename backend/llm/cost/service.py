from ..usage import LLMUsageService
from .models import InvalidPricingError, LLMCostEstimate, LLMModelPricing


class PricingAlreadyRegisteredError(InvalidPricingError):
    """Raised when pricing is registered twice for the same provider/model."""


class UnknownPricingError(KeyError):
    """Raised when no pricing is registered for a provider/model pair."""


class CurrencyMismatchError(ValueError):
    """Raised when a request's usage spans pricing registered in different currencies."""


class LLMCostService:
    """Estimates request cost from normalized usage (Commit #6) and registered pricing.

    Never reads or writes anything on LLMUsageService beyond calling get(),
    so recorded usage is never mutated by cost estimation.
    """

    def __init__(self, usage_service: LLMUsageService):
        self._usage_service = usage_service
        self._pricing = {}

    def register_pricing(self, pricing: LLMModelPricing) -> LLMModelPricing:
        pricing.validate()

        key = (pricing.provider, pricing.model)
        if key in self._pricing:
            raise PricingAlreadyRegisteredError(
                f"pricing already registered for provider={pricing.provider!r} "
                f"model={pricing.model!r}"
            )

        self._pricing[key] = pricing
        return pricing

    def model_cost(self, provider: str, model: str) -> LLMModelPricing:
        try:
            return self._pricing[(provider, model)]
        except KeyError:
            raise UnknownPricingError(
                f"no pricing registered for provider={provider!r} model={model!r}"
            )

    def estimate(self, request_id: str) -> LLMCostEstimate:
        records = self._usage_service.get(request_id)

        input_cost = 0.0
        output_cost = 0.0
        currency = None

        for record in records:
            pricing = self.model_cost(record.provider, record.model)

            if currency is None:
                currency = pricing.currency
            elif currency != pricing.currency:
                raise CurrencyMismatchError(
                    f"request {request_id!r} mixes pricing currencies "
                    f"{currency!r} and {pricing.currency!r}"
                )

            input_cost += record.input_tokens * pricing.input_cost
            output_cost += record.output_tokens * pricing.output_cost

        return LLMCostEstimate(
            request_id=request_id,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
            currency=currency or "USD",
        )
