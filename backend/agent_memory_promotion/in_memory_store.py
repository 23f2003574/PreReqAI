from copy import deepcopy

from .models import LLMAgentMemoryPromotionRecord
from .store import LLMAgentMemoryPromotionStore


class InMemoryLLMAgentMemoryPromotionStore(LLMAgentMemoryPromotionStore):
    """Stores durable LLM agent memory promotion history in memory, for
    development and testing."""

    def __init__(self):
        self._records: dict[str, LLMAgentMemoryPromotionRecord] = {}

    def save(self, record: LLMAgentMemoryPromotionRecord) -> LLMAgentMemoryPromotionRecord:
        stored = deepcopy(record)
        self._records[record.promotion_id] = stored
        return deepcopy(stored)

    def get(self, promotion_id: str):
        record = self._records.get(promotion_id)
        return deepcopy(record) if record is not None else None

    def list_for_memory(self, memory_id: str):
        matching = [record for record in self._records.values() if record.memory_id == memory_id]
        return [deepcopy(record) for record in sorted(matching, key=lambda item: item.decided_at)]
