from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentStrategyOutcome


class LLMAgentStrategyOutcomeStore(ABC):
    """Persistence operations for durable LLM agent strategy outcomes.

    Mirrors backend.agent_memory_feedback.LLMAgentMemoryFeedbackStore's own
    shape -- save/get/list_for_-- rather than introducing a second
    persistence abstraction. There is deliberately no delete() or update():
    an outcome is never overwritten or removed once recorded (see
    LLMAgentStrategyOutcome's own docstring).
    """

    @abstractmethod
    def save(self, outcome: LLMAgentStrategyOutcome) -> LLMAgentStrategyOutcome:
        ...

    @abstractmethod
    def get(self, outcome_id: str) -> Optional[LLMAgentStrategyOutcome]:
        ...

    @abstractmethod
    def list_for_strategy(self, strategy_id: str) -> list:
        ...
