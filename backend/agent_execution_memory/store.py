from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentMemory


class LLMAgentMemoryStore(ABC):
    """Persistence operations for durable LLM agent execution memory.

    Mirrors backend.llm.project_context.LLMProjectContextStore's own
    shape -- save/get/delete/list_for_scope -- rather than introducing a
    second persistence abstraction for what is, mechanically, the same
    kind of scoped, durable record.
    """

    @abstractmethod
    def save(self, memory: LLMAgentMemory) -> LLMAgentMemory:
        ...

    @abstractmethod
    def get(self, memory_id: str) -> Optional[LLMAgentMemory]:
        ...

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str, memory_type: str = None) -> list:
        ...
