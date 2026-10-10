from pathlib import Path

from backend.storage import AtomicJsonFile

from .in_memory_store import DuplicateVersionError
from .models import LLMContextVersion
from .store import LLMContextVersionStore


def _key(context_id: str, version: int) -> str:
    return f"{context_id}::{version}"


class JsonLLMContextVersionStore(LLMContextVersionStore):
    """Persists immutable LLM context versions to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, version: LLMContextVersion) -> LLMContextVersion:
        key = _key(version.context_id, version.version)

        versions = self.file.read()
        if key in versions:
            raise DuplicateVersionError(
                f"version {version.version} already exists for context "
                f"{version.context_id!r}"
            )

        versions[key] = version.to_dict()
        self.file.write(versions)
        return version

    def get(self, context_id: str, version: int):
        versions = self.file.read()
        data = versions.get(_key(context_id, version))
        return None if data is None else LLMContextVersion.from_dict(data)

    def list_for_context(self, context_id: str):
        versions = self.file.read()
        matching = [
            LLMContextVersion.from_dict(data)
            for data in versions.values()
            if data.get("context_id") == context_id
        ]
        return sorted(matching, key=lambda item: item.version)

    def latest_for_context(self, context_id: str):
        matching = self.list_for_context(context_id)
        return matching[-1] if matching else None
