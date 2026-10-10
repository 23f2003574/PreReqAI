from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import TaskContextSnapshot
from .store import TaskContextSnapshotStore


class JsonTaskContextSnapshotStore(TaskContextSnapshotStore):
    """Persists immutable task-context snapshots to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, snapshot: TaskContextSnapshot) -> TaskContextSnapshot:
        snapshots = self.file.read()
        snapshots[snapshot.snapshot_id] = snapshot.to_dict()
        self.file.write(snapshots)
        return snapshot

    def get(self, snapshot_id: str):
        snapshots = self.file.read()
        data = snapshots.get(snapshot_id)
        return None if data is None else TaskContextSnapshot.from_dict(data)

    def list_for_task(self, task_id: str) -> list:
        snapshots = self.file.read()
        matching = [
            TaskContextSnapshot.from_dict(data) for data in snapshots.values() if data.get("task_id") == task_id
        ]
        return sorted(matching, key=lambda item: item.context_version)

    def latest_for_task(self, task_id: str):
        matching = self.list_for_task(task_id)
        return matching[-1] if matching else None
