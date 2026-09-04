from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentPolicy


class LLMAgentPolicyStore(ABC):
    """Persistence operations for durable LLM agent policies.

    Mirrors backend.agent_strategy_library.LLMAgentStrategyStore's own
    save/get/list_for_scope shape rather than introducing a second
    persistence abstraction. There is deliberately no delete(): a policy
    is retired via LLMAgentPolicyService.archive(), which goes through
    save() to flip its status, never a hard delete.
    """

    @abstractmethod
    def save(self, policy: LLMAgentPolicy) -> LLMAgentPolicy:
        ...

    @abstractmethod
    def get(self, policy_id: str) -> Optional[LLMAgentPolicy]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str, status: str = None) -> list:
        ...
