from copy import deepcopy

from .models import LLMAgentRiskProfileVersion
from .store import RiskProfileVersionStore


class InMemoryRiskProfileVersionStore(RiskProfileVersionStore):
    """Stores immutable, append-only risk profile versions in memory,
    for development and testing."""

    def __init__(self):
        self._versions: dict[str, LLMAgentRiskProfileVersion] = {}

    def save(self, version: LLMAgentRiskProfileVersion) -> LLMAgentRiskProfileVersion:
        stored = deepcopy(version)
        self._versions[version.version_id] = stored
        return deepcopy(stored)

    def get(self, version_id: str):
        version = self._versions.get(version_id)
        return deepcopy(version) if version is not None else None

    def list_for_profile(self, profile_id: str):
        matching = [version for version in self._versions.values() if version.profile_id == profile_id]
        return [deepcopy(version) for version in sorted(matching, key=lambda entry: entry.version)]
