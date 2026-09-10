from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import TaskTransitionRecord
from .store import AgentTaskTransitionStore


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
