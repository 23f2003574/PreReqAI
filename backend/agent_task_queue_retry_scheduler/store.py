from abc import ABC, abstractmethod
from typing import Optional

from .models import TaskRetrySchedule


class RetryScheduleStore(ABC):
    """Persistence operations for durable TaskRetrySchedule records,
    one per task_id.

    Mirrors backend.agent_task_queue.AgentTaskQueueStore's own
    save/get/delete/list shape exactly -- the same persistence pattern
    this whole series already uses for every sibling kind of record
    (Rule: "Reuse existing retry/queue persistence").
    """

    @abstractmethod
    def save(self, schedule: TaskRetrySchedule) -> TaskRetrySchedule:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[TaskRetrySchedule]:
        ...

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Remove the schedule for task_id if present. Returns whether
        it was present."""
        ...

    @abstractmethod
    def list(self) -> list:
        """Every currently stored schedule, in no particular order."""
        ...
