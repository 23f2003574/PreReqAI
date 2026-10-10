from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMAgentPolicy
from .store import LLMAgentPolicyStore


class InMemoryLLMAgentPolicyStore(LLMAgentPolicyStore):
    """Stores durable LLM agent policies in memory, for development and testing."""

    def __init__(self):
        self._policies: dict[str, LLMAgentPolicy] = {}

    def save(self, policy: LLMAgentPolicy) -> LLMAgentPolicy:
        policy.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(policy)
        self._policies[policy.policy_id] = stored
        return deepcopy(stored)

    def get(self, policy_id: str):
        policy = self._policies.get(policy_id)
        return deepcopy(policy) if policy is not None else None

    def list_for_scope(self, scope_id: str, status: str = None):
        matching = [
            policy
            for policy in self._policies.values()
            if policy.scope_id == scope_id and (status is None or policy.status == status)
        ]
        return [deepcopy(policy) for policy in sorted(matching, key=lambda item: item.created_at)]
