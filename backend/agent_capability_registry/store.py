from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentCapability


class CapabilityStore(ABC):
    """Persistence operations for durable LLM agent capability records.

    Mirrors backend.agent_policy_templates.LLMAgentPolicyTemplateStore's
    own save/get/list shape -- a capability is never scoped to a single
    project/notebook/API, so list() returns every capability (optionally
    filtered by status), never a list_for_scope(). There is deliberately
    no delete(): a capability is retired via
    LLMAgentCapabilityRegistry.archive(), which goes through save() to
    flip its status, never a hard delete.
    """

    @abstractmethod
    def save(self, capability: LLMAgentCapability) -> LLMAgentCapability:
        ...

    @abstractmethod
    def get(self, capability_id: str) -> Optional[LLMAgentCapability]:
        ...

    @abstractmethod
    def list(self, status: str = None) -> list:
        ...
