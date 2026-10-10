from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentRiskProfileVersion
from .store import RiskProfileVersionStore


class JsonRiskProfileVersionStore(RiskProfileVersionStore):
    """Persists immutable, append-only risk profile versions to a JSON
    file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, version: LLMAgentRiskProfileVersion) -> LLMAgentRiskProfileVersion:
        versions = self.file.read()
        versions[version.version_id] = version.to_dict()
        self.file.write(versions)

        return deepcopy(version)

    def get(self, version_id: str):
        versions = self.file.read()
        data = versions.get(version_id)
        return None if data is None else LLMAgentRiskProfileVersion.from_dict(data)

    def list_for_profile(self, profile_id: str):
        versions = self.file.read()
        matching = [
            LLMAgentRiskProfileVersion.from_dict(data)
            for data in versions.values()
            if data.get("profile_id") == profile_id
        ]
        return sorted(matching, key=lambda entry: entry.version)
