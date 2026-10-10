from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentStrategyLifecycleDecision


class LLMAgentStrategyLifecycleStore(ABC):
    """Persistence operations for durable LLM agent strategy lifecycle decisions.

    Mirrors backend.agent_memory_promotion.LLMAgentMemoryPromotionStore's
    own shape -- save/get/list_for_-- rather than introducing a second
    persistence abstraction. There is deliberately no delete(): a
    lifecycle decision is never overwritten or removed once recorded.
    """

    @abstractmethod
    def save(self, decision: LLMAgentStrategyLifecycleDecision) -> LLMAgentStrategyLifecycleDecision:
        ...

    @abstractmethod
    def get(self, decision_id: str) -> Optional[LLMAgentStrategyLifecycleDecision]:
        ...

    @abstractmethod
    def list_for_strategy(self, strategy_id: str) -> list:
        ...
