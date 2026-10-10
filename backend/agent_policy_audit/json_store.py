from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentPolicyDecisionAudit
from .store import LLMAgentPolicyDecisionAuditStore


class JsonLLMAgentPolicyDecisionAuditStore(LLMAgentPolicyDecisionAuditStore):
    """Persists durable LLM agent policy decision audit records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, audit: LLMAgentPolicyDecisionAudit) -> LLMAgentPolicyDecisionAudit:
        audits = self.file.read()
        audits[audit.audit_id] = audit.to_dict()
        self.file.write(audits)
        return audit

    def get(self, audit_id: str):
        audits = self.file.read()
        data = audits.get(audit_id)
        return None if data is None else LLMAgentPolicyDecisionAudit.from_dict(data)

    def list_for_scope(self, scope_id: str):
        audits = self.file.read()
        matching = [
            LLMAgentPolicyDecisionAudit.from_dict(data)
            for data in audits.values()
            if data.get("scope_id") == scope_id
        ]
        return sorted(matching, key=lambda item: item.created_at)

    def list_for_execution(self, execution_or_action_id: str):
        audits = self.file.read()
        matching = [
            LLMAgentPolicyDecisionAudit.from_dict(data)
            for data in audits.values()
            if data.get("execution_or_action_id") == execution_or_action_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
