from copy import deepcopy

from .models import QueueReservation
from .store import AgentTaskQueueReservationStore


class InMemoryAgentTaskQueueReservationStore(AgentTaskQueueReservationStore):
    """Stores durable QueueReservation records in memory, for
    development and testing. Each instance owns its own dict, so two
    instances never see each other's reservations."""

    def __init__(self):
        self._reservations: dict[str, QueueReservation] = {}

    def save(self, reservation: QueueReservation) -> QueueReservation:
        stored = deepcopy(reservation)
        self._reservations[reservation.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        reservation = self._reservations.get(task_id)
        return deepcopy(reservation) if reservation is not None else None

    def delete(self, task_id: str) -> bool:
        return self._reservations.pop(task_id, None) is not None

    def list(self) -> list:
        return [deepcopy(reservation) for reservation in self._reservations.values()]
