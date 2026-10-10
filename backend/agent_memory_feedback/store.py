from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentMemoryFeedback


class LLMAgentMemoryFeedbackStore(ABC):
    """Persistence operations for durable LLM agent memory feedback.

    Mirrors backend.agent_execution_memory.LLMAgentMemoryStore's own shape
    -- save/get/list_for_-- rather than introducing a second persistence
    abstraction. There is deliberately no delete(): feedback history is
    never overwritten or removed once recorded (see
    LLMAgentMemoryFeedback's own docstring).
    """

    @abstractmethod
    def save(self, feedback: LLMAgentMemoryFeedback) -> LLMAgentMemoryFeedback:
        ...

    @abstractmethod
    def get(self, feedback_id: str) -> Optional[LLMAgentMemoryFeedback]:
        ...

    @abstractmethod
    def list_for_memory(self, memory_id: str) -> list:
        ...
