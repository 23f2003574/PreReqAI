from abc import ABC, abstractmethod
from typing import Optional

from .models import TaskDependency


class TaskDependencyStore(ABC):
    """Persistence operations for durable task dependency edges.

    Mirrors backend.agent_capability_dependencies.DependencyStore's own
    save/get/remove/dependencies_of/dependents_of/all shape exactly, for
    the same graph rather than a second one. There is deliberately no
    update(): an edge is either present or not -- changing what a task
    depends on is remove() then save() of a different edge, never a
    mutation of one in place.
    """

    @abstractmethod
    def save(self, dependency: TaskDependency) -> TaskDependency:
        ...

    @abstractmethod
    def get(self, task_id: str, dependency_task_id: str) -> Optional[TaskDependency]:
        ...

    @abstractmethod
    def remove(self, task_id: str, dependency_task_id: str) -> bool:
        """Remove the edge if present. Returns whether it was present."""
        ...

    @abstractmethod
    def dependencies_of(self, task_id: str) -> list:
        """Every edge where task_id is the dependent (direct dependencies)."""
        ...

    @abstractmethod
    def dependents_of(self, task_id: str) -> list:
        """Every edge where task_id is the prerequisite (direct dependents)."""
        ...

    @abstractmethod
    def all(self) -> list:
        """Every edge ever recorded, for whole-graph operations."""
        ...
