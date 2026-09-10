from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import TaskDependency
from .store import TaskDependencyStore


class JsonTaskDependencyStore(TaskDependencyStore):
    """Persists durable task dependency edges to a JSON file, nested by
    task_id then dependency_task_id."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, dependency: TaskDependency) -> TaskDependency:
        edges = self.file.read()
        edges.setdefault(dependency.task_id, {})[dependency.dependency_task_id] = dependency.to_dict()
        self.file.write(edges)
        return dependency

    def get(self, task_id: str, dependency_task_id: str):
        edges = self.file.read()
        data = edges.get(task_id, {}).get(dependency_task_id)
        return None if data is None else TaskDependency.from_dict(data)

    def remove(self, task_id: str, dependency_task_id: str) -> bool:
        edges = self.file.read()
        removed = edges.get(task_id, {}).pop(dependency_task_id, None) is not None
        if removed:
            self.file.write(edges)
        return removed

    def dependencies_of(self, task_id: str) -> list:
        edges = self.file.read()
        return [TaskDependency.from_dict(data) for data in edges.get(task_id, {}).values()]

    def dependents_of(self, task_id: str) -> list:
        edges = self.file.read()
        return [
            TaskDependency.from_dict(data)
            for by_dependency in edges.values()
            for data in by_dependency.values()
            if data.get("dependency_task_id") == task_id
        ]

    def all(self) -> list:
        edges = self.file.read()
        return [
            TaskDependency.from_dict(data) for by_dependency in edges.values() for data in by_dependency.values()
        ]
