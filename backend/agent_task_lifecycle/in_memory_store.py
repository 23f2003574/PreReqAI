from copy import deepcopy
from datetime import datetime, timezone

from .models import AgentTask
from .store import AgentTaskStore


class InMemoryAgentTaskStore(AgentTaskStore):
    """Stores durable AgentTask lifecycle records in memory, for
    development and testing."""

    def __init__(self):
        self._tasks: dict[str, AgentTask] = {}

    def save(self, task: AgentTask) -> AgentTask:
        task.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(task)
        self._tasks[task.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        task = self._tasks.get(task_id)
        return deepcopy(task) if task is not None else None
