from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentMemoryPromotionRecord


class LLMAgentMemoryPromotionStore(ABC):
    """Persistence operations for durable LLM agent memory promotion history.

    Mirrors backend.agent_memory_feedback.LLMAgentMemoryFeedbackStore's own
    shape -- save/get/list_for_memory -- rather than introducing a second
    persistence abstraction. There is deliberately no delete(): a
    promotion/deprecation decision is never overwritten or removed once
    recorded.
    """

    @abstractmethod
    def save(self, record: LLMAgentMemoryPromotionRecord) -> LLMAgentMemoryPromotionRecord:
        ...

    @abstractmethod
    def get(self, promotion_id: str) -> Optional[LLMAgentMemoryPromotionRecord]:
        ...

    @abstractmethod
    def list_for_memory(self, memory_id: str) -> list:
        ...
