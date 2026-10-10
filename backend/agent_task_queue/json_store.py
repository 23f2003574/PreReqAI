from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import QueueEntry
from .store import AgentTaskQueueStore


class JsonAgentTaskQueueStore(AgentTaskQueueStore):
    """Persists durable QueueEntry records to a JSON file, keyed by
    task_id -- the same AtomicJsonFile-backed, dict-of-id-to-record
    shape every other JSON store in this series already uses (e.g.
    backend.agent_task_lifecycle.JsonAgentTaskStore)."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, entry: QueueEntry) -> QueueEntry:
        entries = self.file.read()
        entries[entry.task_id] = entry.to_dict()
        self.file.write(entries)
        return deepcopy(entry)

    def get(self, task_id: str):
        entries = self.file.read()
        data = entries.get(task_id)
        return None if data is None else QueueEntry.from_dict(data)

    def delete(self, task_id: str) -> bool:
        entries = self.file.read()
        if task_id not in entries:
            return False
        del entries[task_id]
        self.file.write(entries)
        return True

    def list(self) -> list:
        entries = self.file.read()
        return [QueueEntry.from_dict(data) for data in entries.values()]
