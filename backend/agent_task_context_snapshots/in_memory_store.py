from copy import deepcopy

from .models import TaskContextSnapshot
from .store import TaskContextSnapshotStore


class InMemoryTaskContextSnapshotStore(TaskContextSnapshotStore):
    """Stores immutable task-context snapshots in memory, for development and testing."""

    def __init__(self):
        self._snapshots: dict[str, TaskContextSnapshot] = {}

    def save(self, snapshot: TaskContextSnapshot) -> TaskContextSnapshot:
        stored = deepcopy(snapshot)
        self._snapshots[snapshot.snapshot_id] = stored
        return deepcopy(stored)

    def get(self, snapshot_id: str):
        found = self._snapshots.get(snapshot_id)
        return deepcopy(found) if found is not None else None

    def list_for_task(self, task_id: str) -> list:
        matching = [snapshot for snapshot in self._snapshots.values() if snapshot.task_id == task_id]
        return [deepcopy(snapshot) for snapshot in sorted(matching, key=lambda item: item.context_version)]

    def latest_for_task(self, task_id: str):
        snapshots = self.list_for_task(task_id)
        return snapshots[-1] if snapshots else None
