from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentMemoryPromotionRecord
from .store import LLMAgentMemoryPromotionStore


class JsonLLMAgentMemoryPromotionStore(LLMAgentMemoryPromotionStore):
    """Persists durable LLM agent memory promotion history to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: LLMAgentMemoryPromotionRecord) -> LLMAgentMemoryPromotionRecord:
        records = self.file.read()
        records[record.promotion_id] = record.to_dict()
        self.file.write(records)
        return record

    def get(self, promotion_id: str):
        records = self.file.read()
        data = records.get(promotion_id)
        return None if data is None else LLMAgentMemoryPromotionRecord.from_dict(data)

    def list_for_memory(self, memory_id: str):
        records = self.file.read()
        matching = [
            LLMAgentMemoryPromotionRecord.from_dict(data)
            for data in records.values()
            if data.get("memory_id") == memory_id
        ]
        return sorted(matching, key=lambda item: item.decided_at)
