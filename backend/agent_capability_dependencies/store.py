from abc import ABC, abstractmethod
from typing import Optional

from .models import CapabilityDependency


class DependencyStore(ABC):
    """Persistence operations for durable capability dependency edges.

    Mirrors the save/get shape every other store in this series already
    uses; dependencies_of()/dependents_of() play list_for_scope()'s role,
    generalized to a graph's two natural directions. There is
    deliberately no update(): an edge is either present or not --
    changing what a capability depends on is remove() then save() of a
    different edge, never a mutation of one in place.
    """

    @abstractmethod
    def save(self, dependency: CapabilityDependency) -> CapabilityDependency:
        ...

    @abstractmethod
    def get(self, capability_id: str, dependency_id: str) -> Optional[CapabilityDependency]:
        ...

    @abstractmethod
    def remove(self, capability_id: str, dependency_id: str) -> bool:
        """Remove the edge if present. Returns whether it was present."""
        ...

    @abstractmethod
    def dependencies_of(self, capability_id: str) -> list:
        """Every edge where capability_id is the dependent (direct dependencies)."""
        ...

    @abstractmethod
    def dependents_of(self, capability_id: str) -> list:
        """Every edge where capability_id is the prerequisite (direct dependents)."""
        ...

    @abstractmethod
    def all(self) -> list:
        """Every edge ever recorded, for whole-graph operations."""
        ...
