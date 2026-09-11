from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import TaskRetrySchedule
from .store import RetryScheduleStore


class JsonRetryScheduleStore(RetryScheduleStore):
    """Persists durable TaskRetrySchedule records to a JSON file, keyed
    by task_id -- the same AtomicJsonFile-backed shape every other JSON
    store in this series already uses."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, schedule: TaskRetrySchedule) -> TaskRetrySchedule:
        schedules = self.file.read()
        schedules[schedule.task_id] = schedule.to_dict()
        self.file.write(schedules)
        return deepcopy(schedule)

    def get(self, task_id: str):
        schedules = self.file.read()
        data = schedules.get(task_id)
        return None if data is None else TaskRetrySchedule.from_dict(data)

    def delete(self, task_id: str) -> bool:
        schedules = self.file.read()
        if task_id not in schedules:
            return False
        del schedules[task_id]
        self.file.write(schedules)
        return True

    def list(self) -> list:
        schedules = self.file.read()
        return [TaskRetrySchedule.from_dict(data) for data in schedules.values()]
