from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentRiskProfileChange


class RiskProfileHistoryStore(ABC):
    """Persistence operations for durable LLM agent risk profile change
    records.

    Mirrors backend.agent_policy_history.LLMAgentPolicyHistoryStore's
    own shape -- save/get/list_for_ -- with the two lookup indices this
    trail actually needs (list_for_profile, list_for_scope) rather than
    a second persistence abstraction. There is deliberately no delete()
    or update(): a change record is never overwritten or removed once
    recorded.
    """

    @abstractmethod
    def save(self, change: LLMAgentRiskProfileChange) -> LLMAgentRiskProfileChange:
        ...

    @abstractmethod
    def get(self, change_id: str) -> Optional[LLMAgentRiskProfileChange]:
        ...

    @abstractmethod
    def list_for_profile(self, profile_id: str) -> list:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...
