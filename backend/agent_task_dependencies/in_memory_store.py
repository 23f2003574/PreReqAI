from copy import deepcopy

from .models import TaskDependency
from .store import TaskDependencyStore


class InMemoryTaskDependencyStore(TaskDependencyStore):
    """Stores durable task dependency edges in memory, for development
    and testing."""

    def __init__(self):
        self._edges: dict[tuple[str, str], TaskDependency] = {}

    def save(self, dependency: TaskDependency) -> TaskDependency:
        stored = deepcopy(dependency)
        self._edges[(dependency.task_id, dependency.dependency_task_id)] = stored
        return deepcopy(stored)

    def get(self, task_id: str, dependency_task_id: str):
        edge = self._edges.get((task_id, dependency_task_id))
        return deepcopy(edge) if edge is not None else None

    def remove(self, task_id: str, dependency_task_id: str) -> bool:
        return self._edges.pop((task_id, dependency_task_id), None) is not None

    def dependencies_of(self, task_id: str) -> list:
        return [deepcopy(edge) for edge in self._edges.values() if edge.task_id == task_id]

    def dependents_of(self, task_id: str) -> list:
        return [deepcopy(edge) for edge in self._edges.values() if edge.dependency_task_id == task_id]

    def all(self) -> list:
        return [deepcopy(edge) for edge in self._edges.values()]
