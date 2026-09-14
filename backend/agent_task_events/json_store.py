from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import AgentTaskEvent
from .store import AgentTaskEventStore


class JsonAgentTaskEventStore(AgentTaskEventStore):
    """Persists durable AgentTaskEvent records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, event: AgentTaskEvent) -> AgentTaskEvent:
        events = self.file.read()
        events.setdefault(event.task_id, []).append(event.to_dict())
        self.file.write(events)
        return deepcopy(event)

    def list_for_task(self, task_id: str) -> list:
        events = self.file.read()
        matching = [AgentTaskEvent.from_dict(data) for data in events.get(task_id, [])]
        return sorted(matching, key=lambda item: item.occurred_at)
