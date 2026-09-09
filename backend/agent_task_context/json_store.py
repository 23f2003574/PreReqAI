from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentTaskContext
from .store import TaskContextStore


class JsonTaskContextStore(TaskContextStore):
    """Persists durable LLM agent task contexts to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, task_context: LLMAgentTaskContext) -> LLMAgentTaskContext:
        task_context.updated_at = datetime.now(timezone.utc)

        contexts = self.file.read()
        contexts[task_context.task_id] = task_context.to_dict()
        self.file.write(contexts)

        return deepcopy(task_context)

    def get(self, task_id: str):
        contexts = self.file.read()
        data = contexts.get(task_id)
        return None if data is None else LLMAgentTaskContext.from_dict(data)
