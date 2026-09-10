from copy import deepcopy
from datetime import datetime, timezone

from .models import AgentTask, TaskTransitionRecord
from .store import AgentTaskStore, AgentTaskTransitionStore


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


class InMemoryAgentTaskTransitionStore(AgentTaskTransitionStore):
    """Stores durable AgentTask transition history records in memory,
    for development and testing."""

    def __init__(self):
        self._records: dict[str, list] = {}

    def save(self, record: TaskTransitionRecord) -> TaskTransitionRecord:
        stored = deepcopy(record)
        self._records.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str):
        records = self._records.get(task_id, [])
        return [deepcopy(record) for record in sorted(records, key=lambda item: item.occurred_at)]
