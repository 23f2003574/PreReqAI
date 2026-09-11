from abc import ABC, abstractmethod
from typing import Optional

from .models import DeadLetterEntry


class DeadLetterStore(ABC):
    """Persistence operations for durable DeadLetterEntry records, one
    per dead-lettered task_id.

    Mirrors backend.agent_task_queue.AgentTaskQueueStore's own
    save/get/delete/list shape exactly -- the same persistence pattern
    this whole series already uses for every sibling kind of record.
    """

    @abstractmethod
    def save(self, entry: DeadLetterEntry) -> DeadLetterEntry:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[DeadLetterEntry]:
        ...

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Remove the entry for task_id if present. Returns whether it
        was present."""
        ...

    @abstractmethod
    def list(self) -> list:
        """Every currently dead-lettered entry, in no particular
        order."""
        ...
