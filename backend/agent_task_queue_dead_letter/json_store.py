from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import DeadLetterEntry
from .store import DeadLetterStore


class JsonDeadLetterStore(DeadLetterStore):
    """Persists durable DeadLetterEntry records to a JSON file, keyed by
    task_id -- the same AtomicJsonFile-backed shape every other JSON
    store in this series already uses (Rule: "Dead-letter state must
    survive process restarts through existing persistence")."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, entry: DeadLetterEntry) -> DeadLetterEntry:
        entries = self.file.read()
        entries[entry.task_id] = entry.to_dict()
        self.file.write(entries)
        return deepcopy(entry)

    def get(self, task_id: str):
        entries = self.file.read()
        data = entries.get(task_id)
        return None if data is None else DeadLetterEntry.from_dict(data)

    def delete(self, task_id: str) -> bool:
        entries = self.file.read()
        if task_id not in entries:
            return False
        del entries[task_id]
        self.file.write(entries)
        return True

    def list(self) -> list:
        entries = self.file.read()
        return [DeadLetterEntry.from_dict(data) for data in entries.values()]
