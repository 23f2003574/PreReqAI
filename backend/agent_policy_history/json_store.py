from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentPolicyChange
from .store import LLMAgentPolicyHistoryStore


class JsonLLMAgentPolicyHistoryStore(LLMAgentPolicyHistoryStore):
    """Persists durable LLM agent policy change records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, change: LLMAgentPolicyChange) -> LLMAgentPolicyChange:
        changes = self.file.read()
        changes[change.change_id] = change.to_dict()
        self.file.write(changes)
        return change

    def get(self, change_id: str):
        changes = self.file.read()
        data = changes.get(change_id)
        return None if data is None else LLMAgentPolicyChange.from_dict(data)

    def list_for_policy(self, policy_id: str):
        changes = self.file.read()
        matching = [
            LLMAgentPolicyChange.from_dict(data)
            for data in changes.values()
            if data.get("policy_id") == policy_id
        ]
        return sorted(matching, key=lambda item: (item.created_at, item.change_id))

    def list_for_scope(self, scope_id: str):
        changes = self.file.read()
        matching = [
            LLMAgentPolicyChange.from_dict(data)
            for data in changes.values()
            if data.get("scope_id") == scope_id
        ]
        return sorted(matching, key=lambda item: (item.created_at, item.change_id))
