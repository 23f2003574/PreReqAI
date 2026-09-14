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
