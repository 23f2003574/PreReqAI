from copy import deepcopy

from .models import LLMAgentPolicyDeploymentRecord
from .store import LLMAgentPolicyDeploymentHistoryStore


class InMemoryLLMAgentPolicyDeploymentHistoryStore(LLMAgentPolicyDeploymentHistoryStore):
    """Stores durable LLM agent policy deployment records in memory, for
    development and testing."""

    def __init__(self):
        self._records: dict[str, LLMAgentPolicyDeploymentRecord] = {}

    def save(self, record: LLMAgentPolicyDeploymentRecord) -> LLMAgentPolicyDeploymentRecord:
        stored = deepcopy(record)
        self._records[record.deployment_id] = stored
        return deepcopy(stored)

    def get(self, deployment_id: str):
        record = self._records.get(deployment_id)
        return deepcopy(record) if record is not None else None

    def list_for_policy(self, policy_id: str):
        matching = [record for record in self._records.values() if record.policy_id == policy_id]
        return [deepcopy(record) for record in sorted(matching, key=lambda item: item.created_at)]

    def list_for_scope(self, scope_id: str):
        matching = [record for record in self._records.values() if record.target_scope == scope_id]
        return [deepcopy(record) for record in sorted(matching, key=lambda item: item.created_at)]
