from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMAgentStrategy


class LLMAgentStrategyStore(ABC):
    """Persistence operations for durable LLM agent strategies.

    Mirrors backend.llm.project_context.LLMProjectContextStore's own
    shape -- save/get/list_for_scope -- rather than introducing a second
    persistence abstraction for what is, mechanically, the same kind of
    scoped, durable record. There is deliberately no delete(): a strategy
    is retired via LLMAgentStrategyService.archive(), which -- like
    LLMProjectContextService.update() -- goes through save() to flip its
    status, never a hard delete.
    """

    @abstractmethod
    def save(self, strategy: LLMAgentStrategy) -> LLMAgentStrategy:
        ...

    @abstractmethod
    def get(self, strategy_id: str) -> Optional[LLMAgentStrategy]:
        ...

    @abstractmethod
    def list_for_scope(self, scope_id: str, status: str = None) -> list:
        ...
