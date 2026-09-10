from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import AgentTask, TaskTransitionRecord
from .store import AgentTaskStore, AgentTaskTransitionStore


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


class JsonAgentTaskTransitionStore(AgentTaskTransitionStore):
    """Persists durable AgentTask transition history records to a JSON
    file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: TaskTransitionRecord) -> TaskTransitionRecord:
        records = self.file.read()
        records.setdefault(record.task_id, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_task(self, task_id: str):
        records = self.file.read()
        matching = [TaskTransitionRecord.from_dict(data) for data in records.get(task_id, [])]
        return sorted(matching, key=lambda item: item.occurred_at)
