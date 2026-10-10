from dataclasses import dataclass


class InvalidPricingError(ValueError):
    """Raised when an LLMModelPricing fails validation."""


@dataclass(frozen=True)
class LLMModelPricing:
    """Per-token pricing for a specific provider/model pair."""

    provider: str
    model: str
    input_cost: float
    output_cost: float
    currency: str = "USD"

    def validate(self):
        if not self.provider or not isinstance(self.provider, str):
            raise InvalidPricingError("provider is required")

        if not self.model or not isinstance(self.model, str):
            raise InvalidPricingError("model is required")

        if not self.currency or not isinstance(self.currency, str):
            raise InvalidPricingError("currency is required")

        if self.input_cost < 0:
            raise InvalidPricingError("input_cost must not be negative")

        if self.output_cost < 0:
            raise InvalidPricingError("output_cost must not be negative")


@dataclass(frozen=True)
class LLMCostEstimate:
    """A computed, immutable cost estimate for one request's recorded usage."""

    request_id: str
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str
