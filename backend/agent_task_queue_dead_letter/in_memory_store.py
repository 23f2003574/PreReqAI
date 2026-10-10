from copy import deepcopy

from .models import DeadLetterEntry
from .store import DeadLetterStore


class InMemoryDeadLetterStore(DeadLetterStore):
    """Stores durable DeadLetterEntry records in memory, for
    development and testing. Each instance owns its own dict, so two
    instances never see each other's entries."""

    def __init__(self):
        self._entries: dict[str, DeadLetterEntry] = {}

    def save(self, entry: DeadLetterEntry) -> DeadLetterEntry:
        stored = deepcopy(entry)
        self._entries[entry.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        entry = self._entries.get(task_id)
        return deepcopy(entry) if entry is not None else None

    def delete(self, task_id: str) -> bool:
        return self._entries.pop(task_id, None) is not None

    def list(self) -> list:
        return [deepcopy(entry) for entry in self._entries.values()]
