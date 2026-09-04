from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentPolicyChange


class LLMAgentPolicyHistoryStore(ABC):
    """Persistence operations for durable LLM agent policy change records.

    Mirrors backend.agent_strategy_lifecycle.LLMAgentStrategyLifecycleStore's
    own shape -- save/get/list_for_ -- with the two lookup indices this
    trail actually needs (list_for_policy, list_for_scope) rather than a
    second persistence abstraction. There is deliberately no delete() or
    update(): a change record is never overwritten or removed once
    recorded.
    """

    @abstractmethod
    def save(self, change: LLMAgentPolicyChange) -> LLMAgentPolicyChange:
        ...

    @abstractmethod
    def get(self, change_id: str) -> Optional[LLMAgentPolicyChange]:
        ...

    @abstractmethod
    def list_for_policy(self, policy_id: str) -> list:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str) -> list:
        ...
