from copy import deepcopy

from .models import TaskTransitionRecord
from .store import AgentTaskTransitionStore


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
