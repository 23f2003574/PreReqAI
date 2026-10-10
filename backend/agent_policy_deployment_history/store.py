from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentPolicyDeploymentRecord


class LLMAgentPolicyDeploymentHistoryStore(ABC):
    """Persistence operations for durable LLM agent policy deployment
    records.

    Mirrors backend.agent_policy_audit.LLMAgentPolicyDecisionAuditStore's
    own save/get/list_for_-- shape (the closest existing precedent for
    an append-only, id-referencing decision/attempt trail in this
    series) rather than a second persistence abstraction, with the two
    lookup indices this history actually needs (list_for_policy,
    list_for_scope) in place of that store's own list_for_execution.
    There is deliberately no delete() or update(): a deployment record
    is never overwritten or removed once recorded.
    """

    @abstractmethod
    def save(self, record: LLMAgentPolicyDeploymentRecord) -> LLMAgentPolicyDeploymentRecord:
        ...

    @abstractmethod
    def get(self, deployment_id: str) -> Optional[LLMAgentPolicyDeploymentRecord]:
        ...

    @abstractmethod
    def list_for_policy(self, policy_id: str) -> list:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...
