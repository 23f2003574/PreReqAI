from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import QueueReservation
from .store import AgentTaskQueueReservationStore


class JsonAgentTaskQueueReservationStore(AgentTaskQueueReservationStore):
    """Persists durable QueueReservation records to a JSON file, keyed
    by task_id -- the same AtomicJsonFile-backed shape
    backend.agent_task_queue.JsonAgentTaskQueueStore already uses."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, reservation: QueueReservation) -> QueueReservation:
        reservations = self.file.read()
        reservations[reservation.task_id] = reservation.to_dict()
        self.file.write(reservations)
        return deepcopy(reservation)

    def get(self, task_id: str):
        reservations = self.file.read()
        data = reservations.get(task_id)
        return None if data is None else QueueReservation.from_dict(data)

    def delete(self, task_id: str) -> bool:
        reservations = self.file.read()
        if task_id not in reservations:
            return False
        del reservations[task_id]
        self.file.write(reservations)
        return True

    def list(self) -> list:
        reservations = self.file.read()
        return [QueueReservation.from_dict(data) for data in reservations.values()]
