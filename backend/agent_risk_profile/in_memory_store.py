from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMAgentRiskProfile
from .store import RiskProfileStore


class InMemoryRiskProfileStore(RiskProfileStore):
    """Stores durable LLM agent risk profiles in memory, for development
    and testing."""

    def __init__(self):
        self._profiles: dict[str, LLMAgentRiskProfile] = {}

    def save(self, profile: LLMAgentRiskProfile) -> LLMAgentRiskProfile:
        profile.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(profile)
        self._profiles[profile.profile_id] = stored
        return deepcopy(stored)

    def get(self, profile_id: str):
        profile = self._profiles.get(profile_id)
        return deepcopy(profile) if profile is not None else None

    def list_for_scope(self, scope_id: str, status: str = None):
        matching = [
            profile
            for profile in self._profiles.values()
            if profile.scope_id == scope_id and (status is None or profile.status == status)
        ]
        return [deepcopy(profile) for profile in sorted(matching, key=lambda item: item.created_at)]
