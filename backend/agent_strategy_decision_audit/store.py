from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentStrategyDecision


class LLMAgentStrategyDecisionStore(ABC):
    """Persistence operations for durable LLM agent strategy decision audit records.

    Mirrors backend.agent_strategy_usage.LLMAgentStrategyUsageStore's own
    shape -- save/get/list_for_-- extended with the same second lookup
    index (list_for_execution) that module already uses, since a
    decision, like a usage record, is queried from both directions: every
    decision about one strategy, and every decision made for one
    execution/task. There is deliberately no delete() or update(): a
    decision is never overwritten or removed once recorded.
    """

    @abstractmethod
    def save(self, decision: LLMAgentStrategyDecision) -> LLMAgentStrategyDecision:
        ...

    @abstractmethod
    def get(self, decision_id: str) -> Optional[LLMAgentStrategyDecision]:
        ...

    @abstractmethod
    def list_for_strategy(self, strategy_id: str) -> list:
        ...

    @abstractmethod
    def list_for_execution(self, execution_or_task_id: str) -> list:
        ...
