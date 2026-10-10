from copy import deepcopy
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentPolicyDeploymentRecord
from .store import LLMAgentPolicyDeploymentHistoryStore


class JsonLLMAgentPolicyDeploymentHistoryStore(LLMAgentPolicyDeploymentHistoryStore):
    """Persists durable LLM agent policy deployment records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: LLMAgentPolicyDeploymentRecord) -> LLMAgentPolicyDeploymentRecord:
        records = self.file.read()
        records[record.deployment_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, deployment_id: str):
        records = self.file.read()
        data = records.get(deployment_id)
        return None if data is None else LLMAgentPolicyDeploymentRecord.from_dict(data)

    def list_for_policy(self, policy_id: str):
        records = self.file.read()
        matching = [
            LLMAgentPolicyDeploymentRecord.from_dict(data)
            for data in records.values()
            if data.get("policy_id") == policy_id
        ]
        return sorted(matching, key=lambda item: item.created_at)

    def list_for_scope(self, scope_id: str):
        records = self.file.read()
        matching = [
            LLMAgentPolicyDeploymentRecord.from_dict(data)
            for data in records.values()
            if data.get("target_scope") == scope_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
