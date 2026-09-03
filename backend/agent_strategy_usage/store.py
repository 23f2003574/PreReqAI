from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentStrategyUsage


class LLMAgentStrategyUsageStore(ABC):
    """Persistence operations for durable LLM agent strategy usage records.

    Mirrors backend.agent_strategy_effectiveness.LLMAgentStrategyOutcomeStore's
    own shape -- save/get/list_for_-- rather than introducing a second
    persistence abstraction, extended with a second lookup index
    (list_for_execution) since usage, unlike an outcome, is queried from
    both directions: which strategies were used in one execution, and
    where one strategy was used. There is deliberately no delete() or
    update(): a usage record is never overwritten or removed once
    recorded (see LLMAgentStrategyUsage's own docstring).
    """

    @abstractmethod
    def save(self, usage: LLMAgentStrategyUsage) -> LLMAgentStrategyUsage:
        ...

    @abstractmethod
    def get(self, usage_id: str) -> Optional[LLMAgentStrategyUsage]:
        ...

    @abstractmethod
    def list_for_strategy(self, strategy_id: str) -> list:
        ...

    @abstractmethod
    def list_for_execution(self, execution_id: str) -> list:
        ...
