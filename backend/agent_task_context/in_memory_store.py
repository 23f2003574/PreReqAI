from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMAgentTaskContext
from .store import TaskContextStore


class InMemoryTaskContextStore(TaskContextStore):
    """Stores durable LLM agent task contexts in memory, for development
    and testing."""

    def __init__(self):
        self._contexts: dict[str, LLMAgentTaskContext] = {}

    def save(self, task_context: LLMAgentTaskContext) -> LLMAgentTaskContext:
        task_context.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(task_context)
        self._contexts[task_context.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        task_context = self._contexts.get(task_id)
        return deepcopy(task_context) if task_context is not None else None
