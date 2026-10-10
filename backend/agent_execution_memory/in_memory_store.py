from copy import deepcopy

from .models import LLMAgentMemory
from .store import LLMAgentMemoryStore


class InMemoryLLMAgentMemoryStore(LLMAgentMemoryStore):
    """Stores durable LLM agent execution memory in memory, for development and testing."""

    def __init__(self):
        self._memories: dict[str, LLMAgentMemory] = {}

    def save(self, memory: LLMAgentMemory) -> LLMAgentMemory:
        stored = deepcopy(memory)
        self._memories[memory.memory_id] = stored
        return deepcopy(stored)

    def get(self, memory_id: str):
        memory = self._memories.get(memory_id)
        return deepcopy(memory) if memory is not None else None

    def delete(self, memory_id: str) -> bool:
        if memory_id not in self._memories:
            return False
        del self._memories[memory_id]
        return True

    def list_for_scope(self, scope_id: str, memory_type: str = None):
        matching = [
            memory
            for memory in self._memories.values()
            if memory.scope_id == scope_id
            and (memory_type is None or memory.memory_type == memory_type)
        ]
        return [
            deepcopy(memory)
            for memory in sorted(matching, key=lambda item: item.created_at)
        ]
