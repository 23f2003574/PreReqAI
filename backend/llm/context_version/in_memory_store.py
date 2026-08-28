from copy import deepcopy

from .models import LLMContextVersion
from .store import LLMContextVersionStore


class DuplicateVersionError(ValueError):
    """Raised if a (context_id, version) pair is saved more than once.

    Versions are immutable, so a store must refuse to overwrite one that
    already exists rather than silently replacing it.
    """


class InMemoryLLMContextVersionStore(LLMContextVersionStore):
    """Stores immutable LLM context versions in memory, for development and testing."""

    def __init__(self):
        self._versions: dict[tuple[str, int], LLMContextVersion] = {}

    def save(self, version: LLMContextVersion) -> LLMContextVersion:
        key = (version.context_id, version.version)
        if key in self._versions:
            raise DuplicateVersionError(
                f"version {version.version} already exists for context "
                f"{version.context_id!r}"
            )

        stored = deepcopy(version)
        self._versions[key] = stored
        return deepcopy(stored)

    def get(self, context_id: str, version: int):
        found = self._versions.get((context_id, version))
        return deepcopy(found) if found is not None else None

    def list_for_context(self, context_id: str):
        matching = [
            entry for entry in self._versions.values() if entry.context_id == context_id
        ]
        return [
            deepcopy(entry) for entry in sorted(matching, key=lambda item: item.version)
        ]

    def latest_for_context(self, context_id: str):
        versions = self.list_for_context(context_id)
        return versions[-1] if versions else None
