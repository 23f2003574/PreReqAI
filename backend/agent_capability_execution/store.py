from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentCapabilityExecution


class ExecutionStore(ABC):
    """Persistence operations for durable capability execution records.

    Mirrors every other store in this series' own save/get shape;
    list_for_agent()/list_for_capability() play list_for_scope()'s role,
    one per way this service's own spec asks records to be filtered.
    There is deliberately no delete(): an execution record, once
    started, is retained for its full lifecycle and beyond -- save() is
    always how a status transition is persisted (a new, replaced
    instance from the same execution_id), never a hard delete.
    """

    @abstractmethod
    def save(self, execution: LLMAgentCapabilityExecution) -> LLMAgentCapabilityExecution:
        ...

    @abstractmethod
    def get(self, execution_id: str) -> Optional[LLMAgentCapabilityExecution]:
        ...

    @abstractmethod
    def list_for_agent(self, agent_id: str) -> list:
        ...

    @abstractmethod
    def list_for_capability(self, capability_id: str) -> list:
        ...
