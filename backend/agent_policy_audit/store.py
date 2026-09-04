from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentPolicyDecisionAudit


class LLMAgentPolicyDecisionAuditStore(ABC):
    """Persistence operations for durable LLM agent policy decision audit records.

    Mirrors backend.agent_strategy_decision_audit.LLMAgentStrategyDecisionStore's
    own shape -- save/get/list_for_ -- with the two lookup indices this
    audit trail actually needs (list_for_scope, list_for_execution)
    rather than introducing a third persistence abstraction. There is
    deliberately no delete() or update(): a decision audit record is
    never overwritten or removed once recorded.
    """

    @abstractmethod
    def save(self, audit: LLMAgentPolicyDecisionAudit) -> LLMAgentPolicyDecisionAudit:
        ...

    @abstractmethod
    def get(self, audit_id: str) -> Optional[LLMAgentPolicyDecisionAudit]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...

    @abstractmethod
    def list_for_execution(self, execution_or_action_id: str) -> list:
        ...
