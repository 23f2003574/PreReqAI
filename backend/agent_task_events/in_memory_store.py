from copy import deepcopy

from .models import AgentTaskEvent
from .store import AgentTaskEventStore


class InMemoryAgentTaskEventStore(AgentTaskEventStore):
    """Stores durable AgentTaskEvent records in memory, for development
    and testing."""

    def __init__(self):
        self._events: dict[str, list] = {}

    def save(self, event: AgentTaskEvent) -> AgentTaskEvent:
        stored = deepcopy(event)
        self._events.setdefault(event.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str) -> list:
        events = self._events.get(task_id, [])
        return [deepcopy(event) for event in sorted(events, key=lambda item: item.occurred_at)]

    def all(self) -> list:
        every_event = [event for events in self._events.values() for event in events]
        return [deepcopy(event) for event in sorted(every_event, key=lambda item: item.occurred_at)]

    def delete(self, task_id: str, event_id: str) -> bool:
        events = self._events.get(task_id)
        if not events:
            return False
        for index, event in enumerate(events):
            if event.event_id == event_id:
                del events[index]
                return True
        return False
