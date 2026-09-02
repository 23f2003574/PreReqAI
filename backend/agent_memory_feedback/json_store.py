from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentMemoryFeedback
from .store import LLMAgentMemoryFeedbackStore


class JsonLLMAgentMemoryFeedbackStore(LLMAgentMemoryFeedbackStore):
    """Persists durable LLM agent memory feedback to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, feedback: LLMAgentMemoryFeedback) -> LLMAgentMemoryFeedback:
        records = self.file.read()
        records[feedback.feedback_id] = feedback.to_dict()
        self.file.write(records)
        return feedback

    def get(self, feedback_id: str):
        records = self.file.read()
        data = records.get(feedback_id)
        return None if data is None else LLMAgentMemoryFeedback.from_dict(data)

    def list_for_memory(self, memory_id: str):
        records = self.file.read()
        matching = [
            LLMAgentMemoryFeedback.from_dict(data)
            for data in records.values()
            if data.get("memory_id") == memory_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
