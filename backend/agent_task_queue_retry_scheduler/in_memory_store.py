from copy import deepcopy

from .models import TaskRetrySchedule
from .store import RetryScheduleStore


class InMemoryRetryScheduleStore(RetryScheduleStore):
    """Stores durable TaskRetrySchedule records in memory, for
    development and testing. Each instance owns its own dict, so two
    instances never see each other's schedules."""

    def __init__(self):
        self._schedules: dict[str, TaskRetrySchedule] = {}

    def save(self, schedule: TaskRetrySchedule) -> TaskRetrySchedule:
        stored = deepcopy(schedule)
        self._schedules[schedule.task_id] = stored
        return deepcopy(stored)

    def get(self, task_id: str):
        schedule = self._schedules.get(task_id)
        return deepcopy(schedule) if schedule is not None else None

    def delete(self, task_id: str) -> bool:
        return self._schedules.pop(task_id, None) is not None

    def list(self) -> list:
        return [deepcopy(schedule) for schedule in self._schedules.values()]
