from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentPolicyException


class LLMAgentPolicyExceptionStore(ABC):
    """Persistence operations for durable LLM agent policy exceptions.

    Mirrors backend.agent_policy_engine.LLMAgentPolicyStore's own
    save/get/list_for_scope shape rather than introducing a second
    persistence abstraction. There is deliberately no delete(): an
    exception is retired via LLMAgentPolicyExceptionService.revoke(),
    which goes through save() to flip its status, never a hard delete --
    the same "never erase, only retire" discipline
    backend.session.execution_policy_risk_override.ExecutionPolicyRiskOverrideService
    already applies to a revoked override.
    """

    @abstractmethod
    def save(self, exception: LLMAgentPolicyException) -> LLMAgentPolicyException:
        ...

    @abstractmethod
    def get(self, exception_id: str) -> Optional[LLMAgentPolicyException]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str, status: str = None) -> list:
        ...
