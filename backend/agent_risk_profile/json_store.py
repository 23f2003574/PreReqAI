from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentRiskProfile
from .store import RiskProfileStore


class JsonRiskProfileStore(RiskProfileStore):
    """Persists durable LLM agent risk profiles to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, profile: LLMAgentRiskProfile) -> LLMAgentRiskProfile:
        profile.updated_at = datetime.now(timezone.utc)

        profiles = self.file.read()
        profiles[profile.profile_id] = profile.to_dict()
        self.file.write(profiles)

        return deepcopy(profile)

    def get(self, profile_id: str):
        profiles = self.file.read()
        data = profiles.get(profile_id)
        return None if data is None else LLMAgentRiskProfile.from_dict(data)

    def list_for_scope(self, scope_id: str, status: str = None):
        profiles = self.file.read()
        matching = [
            LLMAgentRiskProfile.from_dict(data)
            for data in profiles.values()
            if data.get("scope_id") == scope_id and (status is None or data.get("status") == status)
        ]
        return sorted(matching, key=lambda item: item.created_at)
