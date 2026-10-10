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

    def all(self) -> list:
        events = self.file.read()
        every_event = [AgentTaskEvent.from_dict(data) for records in events.values() for data in records]
        return sorted(every_event, key=lambda item: item.occurred_at)

    def delete(self, task_id: str, event_id: str) -> bool:
        events = self.file.read()
        task_events = events.get(task_id)
        if not task_events:
            return False
        for index, data in enumerate(task_events):
            if data.get("event_id") == event_id:
                del task_events[index]
                self.file.write(events)
                return True
        return False
