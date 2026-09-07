from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentRiskProfile


class RiskProfileStore(ABC):
    """Persistence operations for durable LLM agent risk profiles.

    Mirrors backend.agent_policy_engine.LLMAgentPolicyStore's own
    save/get/list_for_scope shape rather than introducing a second
    persistence abstraction. There is deliberately no delete(): a
    profile is retired via LLMAgentRiskProfileService.archive(), which
    goes through save() to flip its status, never a hard delete.
    """

    @abstractmethod
    def save(self, profile: LLMAgentRiskProfile) -> LLMAgentRiskProfile:
        ...

    @abstractmethod
    def get(self, profile_id: str) -> Optional[LLMAgentRiskProfile]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str, status: str = None) -> list:
        ...
