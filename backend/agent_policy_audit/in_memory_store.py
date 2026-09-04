from copy import deepcopy

from .models import LLMAgentPolicyDecisionAudit
from .store import LLMAgentPolicyDecisionAuditStore


class InMemoryLLMAgentPolicyDecisionAuditStore(LLMAgentPolicyDecisionAuditStore):
    """Stores durable LLM agent policy decision audit records in memory,
    for development and testing."""

    def __init__(self):
        self._audits: dict[str, LLMAgentPolicyDecisionAudit] = {}

    def save(self, audit: LLMAgentPolicyDecisionAudit) -> LLMAgentPolicyDecisionAudit:
        stored = deepcopy(audit)
        self._audits[audit.audit_id] = stored
        return deepcopy(stored)

    def get(self, audit_id: str):
        audit = self._audits.get(audit_id)
        return deepcopy(audit) if audit is not None else None

    def list_for_scope(self, scope_id: str):
        matching = [audit for audit in self._audits.values() if audit.scope_id == scope_id]
        return [deepcopy(audit) for audit in sorted(matching, key=lambda item: item.created_at)]

    def list_for_execution(self, execution_or_action_id: str):
        matching = [
            audit for audit in self._audits.values() if audit.execution_or_action_id == execution_or_action_id
        ]
        return [deepcopy(audit) for audit in sorted(matching, key=lambda item: item.created_at)]
