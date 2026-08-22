from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMRouteRequest:
    """Describes what a caller needs so a provider/model can be selected."""

    task: str
    preferred_provider: Optional[str] = None
    required_capabilities: list = field(default_factory=list)
    max_cost: Optional[float] = None
    max_latency: Optional[float] = None

    def validate(self):
        if not self.task or not isinstance(self.task, str):
            raise ValueError("LLMRouteRequest.task is required")

        if self.max_cost is not None and self.max_cost < 0:
            raise ValueError("LLMRouteRequest.max_cost must not be negative")

        if self.max_latency is not None and self.max_latency < 0:
            raise ValueError("LLMRouteRequest.max_latency must not be negative")


@dataclass
class LLMRoute:
    """A resolved provider/model choice for a route request."""

    provider: str
    model: str
    score: float
    reason: str


@dataclass
class ProviderCapabilityProfile:
    """Static routing metadata for a provider: what it can do, at what cost."""

    capabilities: frozenset
    cost: float = 0.0
    latency: float = 0.0

    def __post_init__(self):
        self.capabilities = frozenset(self.capabilities)
