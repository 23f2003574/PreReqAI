from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentPolicy
from .store import LLMAgentPolicyStore


class JsonLLMAgentPolicyStore(LLMAgentPolicyStore):
    """Persists durable LLM agent policies to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, policy: LLMAgentPolicy) -> LLMAgentPolicy:
        policy.updated_at = datetime.now(timezone.utc)

        policies = self.file.read()
        policies[policy.policy_id] = policy.to_dict()
        self.file.write(policies)

        return deepcopy(policy)

    def get(self, policy_id: str):
        policies = self.file.read()
        data = policies.get(policy_id)
        return None if data is None else LLMAgentPolicy.from_dict(data)

    def list_for_scope(self, scope_id: str, status: str = None):
        policies = self.file.read()
        matching = [
            LLMAgentPolicy.from_dict(data)
            for data in policies.values()
            if data.get("scope_id") == scope_id and (status is None or data.get("status") == status)
        ]
        return sorted(matching, key=lambda item: item.created_at)
