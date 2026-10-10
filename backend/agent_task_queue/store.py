from abc import ABC, abstractmethod
from typing import Optional

from .models import QueueEntry


class AgentTaskQueueStore(ABC):
    """Persistence operations for durable QueueEntry records, one per
    queued task_id.

    Mirrors backend.agent_task_lifecycle.AgentTaskStore's own save/get
    shape, extended with delete()/list() the same way backend.
    agent_execution_memory.LLMAgentMemoryStore already extends save/get
    with delete()/list_for_scope() for its own store -- not a second
    persistence abstraction.
    """

    @abstractmethod
    def save(self, entry: QueueEntry) -> QueueEntry:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[QueueEntry]:
        ...

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Remove the entry for task_id if present. Returns whether it
        was present."""
        ...

    @abstractmethod
    def list(self) -> list:
        """Every currently queued entry, in no particular order --
        ordering for consumption is LLMAgentTaskQueueService.peek()'s
        own job, not the store's."""
        ...
