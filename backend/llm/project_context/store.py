from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMProjectContext


class LLMProjectContextStore(ABC):
    """Persistence operations for durable LLM project context.

    Same shape as backend.session's ResearchArtifactStore: save/get/delete
    plus a scoped listing method, implemented once in memory and once atop
    backend.storage.AtomicJsonFile.
    """

    @abstractmethod
    def save(self, context: LLMProjectContext) -> LLMProjectContext:
        raise NotImplementedError

    @abstractmethod
    def get(self, context_id: str) -> Optional[LLMProjectContext]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, context_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_for_scope(
        self, scope_id: str, context_type: Optional[str] = None
    ) -> list:
        raise NotImplementedError
