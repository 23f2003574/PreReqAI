from abc import ABC, abstractmethod
from typing import Optional

from .models import QueueReservation


class AgentTaskQueueReservationStore(ABC):
    """Persistence operations for durable QueueReservation records, one
    per reserved task_id.

    Mirrors backend.agent_task_queue.AgentTaskQueueStore's own
    save/get/delete/list shape exactly -- the same persistence pattern,
    for a sibling kind of record, not a second abstraction.
    """

    @abstractmethod
    def save(self, reservation: QueueReservation) -> QueueReservation:
        ...

    @abstractmethod
    def get(self, task_id: str) -> Optional[QueueReservation]:
        ...

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Remove the reservation for task_id if present. Returns
        whether it was present."""
        ...

    @abstractmethod
    def list(self) -> list:
        """Every currently stored reservation, in no particular order."""
        ...
