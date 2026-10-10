from copy import deepcopy

from .models import LLMAgentMemoryFeedback
from .store import LLMAgentMemoryFeedbackStore


class InMemoryLLMAgentMemoryFeedbackStore(LLMAgentMemoryFeedbackStore):
    """Stores durable LLM agent memory feedback in memory, for development and testing."""

    def __init__(self):
        self._feedback: dict[str, LLMAgentMemoryFeedback] = {}

    def save(self, feedback: LLMAgentMemoryFeedback) -> LLMAgentMemoryFeedback:
        stored = deepcopy(feedback)
        self._feedback[feedback.feedback_id] = stored
        return deepcopy(stored)

    def get(self, feedback_id: str):
        feedback = self._feedback.get(feedback_id)
        return deepcopy(feedback) if feedback is not None else None

    def list_for_memory(self, memory_id: str):
        matching = [feedback for feedback in self._feedback.values() if feedback.memory_id == memory_id]
        return [deepcopy(feedback) for feedback in sorted(matching, key=lambda item: item.created_at)]
