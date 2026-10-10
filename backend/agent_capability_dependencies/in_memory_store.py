from copy import deepcopy

from .models import CapabilityDependency
from .store import DependencyStore


class InMemoryDependencyStore(DependencyStore):
    """Stores durable capability dependency edges in memory, for
    development and testing."""

    def __init__(self):
        self._edges: dict[tuple[str, str], CapabilityDependency] = {}

    def save(self, dependency: CapabilityDependency) -> CapabilityDependency:
        stored = deepcopy(dependency)
        self._edges[(dependency.capability_id, dependency.dependency_id)] = stored
        return deepcopy(stored)

    def get(self, capability_id: str, dependency_id: str):
        edge = self._edges.get((capability_id, dependency_id))
        return deepcopy(edge) if edge is not None else None

    def remove(self, capability_id: str, dependency_id: str) -> bool:
        return self._edges.pop((capability_id, dependency_id), None) is not None

    def dependencies_of(self, capability_id: str) -> list:
        return [deepcopy(edge) for edge in self._edges.values() if edge.capability_id == capability_id]

    def dependents_of(self, capability_id: str) -> list:
        return [deepcopy(edge) for edge in self._edges.values() if edge.dependency_id == capability_id]

    def all(self) -> list:
        return [deepcopy(edge) for edge in self._edges.values()]
