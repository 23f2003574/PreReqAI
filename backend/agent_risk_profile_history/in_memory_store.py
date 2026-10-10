from copy import deepcopy

from .models import LLMAgentRiskProfileChange
from .store import RiskProfileHistoryStore


class InMemoryRiskProfileHistoryStore(RiskProfileHistoryStore):
    """Stores durable LLM agent risk profile change records in memory,
    for development and testing."""

    def __init__(self):
        self._changes: dict[str, LLMAgentRiskProfileChange] = {}

    def save(self, change: LLMAgentRiskProfileChange) -> LLMAgentRiskProfileChange:
        stored = deepcopy(change)
        self._changes[change.change_id] = stored
        return deepcopy(stored)

    def get(self, change_id: str):
        change = self._changes.get(change_id)
        return deepcopy(change) if change is not None else None

    def list_for_profile(self, profile_id: str):
        matching = [change for change in self._changes.values() if change.profile_id == profile_id]
        return [deepcopy(change) for change in sorted(matching, key=lambda item: (item.created_at, item.change_id))]

    def list_for_scope(self, scope_id: str):
        matching = [change for change in self._changes.values() if change.scope_id == scope_id]
        return [deepcopy(change) for change in sorted(matching, key=lambda item: (item.created_at, item.change_id))]
