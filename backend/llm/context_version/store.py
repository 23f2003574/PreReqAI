from abc import ABC, abstractmethod
from typing import Optional

from .models import LLMContextVersion


class LLMContextVersionStore(ABC):
    """Persistence operations for immutable LLM context versions.

    Same save/get/list shape as backend.llm.project_context's store, plus a
    latest_for_context lookup -- there is no update: a version, once saved,
    is never replaced.
    """

    @abstractmethod
    def save(self, version: LLMContextVersion) -> LLMContextVersion:
        raise NotImplementedError

    @abstractmethod
    def get(self, context_id: str, version: int) -> Optional[LLMContextVersion]:
        raise NotImplementedError

    @abstractmethod
    def list_for_context(self, context_id: str) -> list:
        raise NotImplementedError

    @abstractmethod
    def latest_for_context(self, context_id: str) -> Optional[LLMContextVersion]:
        raise NotImplementedError
