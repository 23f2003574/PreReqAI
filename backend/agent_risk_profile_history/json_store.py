from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentRiskProfileChange
from .store import RiskProfileHistoryStore


class JsonRiskProfileHistoryStore(RiskProfileHistoryStore):
    """Persists durable LLM agent risk profile change records to a JSON
    file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, change: LLMAgentRiskProfileChange) -> LLMAgentRiskProfileChange:
        changes = self.file.read()
        changes[change.change_id] = change.to_dict()
        self.file.write(changes)
        return change

    def get(self, change_id: str):
        changes = self.file.read()
        data = changes.get(change_id)
        return None if data is None else LLMAgentRiskProfileChange.from_dict(data)

    def list_for_profile(self, profile_id: str):
        changes = self.file.read()
        matching = [
            LLMAgentRiskProfileChange.from_dict(data)
            for data in changes.values()
            if data.get("profile_id") == profile_id
        ]
        return sorted(matching, key=lambda item: (item.created_at, item.change_id))

    def list_for_scope(self, scope_id: str):
        changes = self.file.read()
        matching = [
            LLMAgentRiskProfileChange.from_dict(data)
            for data in changes.values()
            if data.get("scope_id") == scope_id
        ]
        return sorted(matching, key=lambda item: (item.created_at, item.change_id))
