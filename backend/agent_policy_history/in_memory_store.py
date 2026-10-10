from copy import deepcopy

from .models import LLMAgentPolicyChange
from .store import LLMAgentPolicyHistoryStore


class InMemoryLLMAgentPolicyHistoryStore(LLMAgentPolicyHistoryStore):
    """Stores durable LLM agent policy change records in memory, for
    development and testing."""

    def __init__(self):
        self._changes: dict[str, LLMAgentPolicyChange] = {}

    def save(self, change: LLMAgentPolicyChange) -> LLMAgentPolicyChange:
        stored = deepcopy(change)
        self._changes[change.change_id] = stored
        return deepcopy(stored)

    def get(self, change_id: str):
        change = self._changes.get(change_id)
        return deepcopy(change) if change is not None else None

    def list_for_policy(self, policy_id: str):
        matching = [change for change in self._changes.values() if change.policy_id == policy_id]
        return [deepcopy(change) for change in sorted(matching, key=lambda item: (item.created_at, item.change_id))]

    def list_for_scope(self, scope_id: str):
        matching = [change for change in self._changes.values() if change.scope_id == scope_id]
        return [deepcopy(change) for change in sorted(matching, key=lambda item: (item.created_at, item.change_id))]
