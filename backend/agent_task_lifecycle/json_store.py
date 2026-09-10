from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import AgentTask
from .store import AgentTaskStore


class JsonAgentTaskStore(AgentTaskStore):
    """Persists durable AgentTask lifecycle records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, task: AgentTask) -> AgentTask:
        task.updated_at = datetime.now(timezone.utc)

        tasks = self.file.read()
        tasks[task.task_id] = task.to_dict()
        self.file.write(tasks)

        return deepcopy(task)

    def get(self, task_id: str):
        tasks = self.file.read()
        data = tasks.get(task_id)
        return None if data is None else AgentTask.from_dict(data)
