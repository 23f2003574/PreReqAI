from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentMemory
from .store import LLMAgentMemoryStore


class JsonLLMAgentMemoryStore(LLMAgentMemoryStore):
    """Persists durable LLM agent execution memory to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, memory: LLMAgentMemory) -> LLMAgentMemory:
        memories = self.file.read()
        memories[memory.memory_id] = memory.to_dict()
        self.file.write(memories)
        return memory

    def get(self, memory_id: str):
        memories = self.file.read()
        data = memories.get(memory_id)
        return None if data is None else LLMAgentMemory.from_dict(data)

    def delete(self, memory_id: str) -> bool:
        memories = self.file.read()
        if memory_id not in memories:
            return False
        del memories[memory_id]
        self.file.write(memories)
        return True

    def list_for_scope(self, scope_id: str, memory_type: str = None):
        memories = self.file.read()
        matching = [
            LLMAgentMemory.from_dict(data)
            for data in memories.values()
            if data.get("scope_id") == scope_id
            and (memory_type is None or data.get("memory_type") == memory_type)
        ]
        return sorted(matching, key=lambda item: item.created_at)
