from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import CapabilityDependency
from .store import DependencyStore


class JsonDependencyStore(DependencyStore):
    """Persists durable capability dependency edges to a JSON file,
    nested by capability_id then dependency_id."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, dependency: CapabilityDependency) -> CapabilityDependency:
        edges = self.file.read()
        edges.setdefault(dependency.capability_id, {})[dependency.dependency_id] = dependency.to_dict()
        self.file.write(edges)
        return dependency

    def get(self, capability_id: str, dependency_id: str):
        edges = self.file.read()
        data = edges.get(capability_id, {}).get(dependency_id)
        return None if data is None else CapabilityDependency.from_dict(data)

    def remove(self, capability_id: str, dependency_id: str) -> bool:
        edges = self.file.read()
        removed = edges.get(capability_id, {}).pop(dependency_id, None) is not None
        if removed:
            self.file.write(edges)
        return removed

    def dependencies_of(self, capability_id: str) -> list:
        edges = self.file.read()
        return [CapabilityDependency.from_dict(data) for data in edges.get(capability_id, {}).values()]

    def dependents_of(self, capability_id: str) -> list:
        edges = self.file.read()
        return [
            CapabilityDependency.from_dict(data)
            for by_dependency in edges.values()
            for data in by_dependency.values()
            if data.get("dependency_id") == capability_id
        ]

    def all(self) -> list:
        edges = self.file.read()
        return [
            CapabilityDependency.from_dict(data)
            for by_dependency in edges.values()
            for data in by_dependency.values()
        ]
