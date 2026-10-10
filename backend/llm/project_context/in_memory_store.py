from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMProjectContext
from .store import LLMProjectContextStore


class InMemoryLLMProjectContextStore(LLMProjectContextStore):
    """Stores durable LLM project context in memory, for development and testing."""

    def __init__(self):
        self._contexts: dict[str, LLMProjectContext] = {}

    def save(self, context: LLMProjectContext) -> LLMProjectContext:
        context.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(context)
        self._contexts[context.context_id] = stored
        return deepcopy(stored)

    def get(self, context_id: str):
        context = self._contexts.get(context_id)
        return deepcopy(context) if context is not None else None

    def delete(self, context_id: str) -> bool:
        if context_id not in self._contexts:
            return False
        del self._contexts[context_id]
        return True

    def list_for_scope(self, scope_id: str, context_type=None):
        matching = [
            context
            for context in self._contexts.values()
            if context.scope_id == scope_id
            and (context_type is None or context.context_type == context_type)
        ]
        return [
            deepcopy(context)
            for context in sorted(matching, key=lambda item: item.created_at)
        ]
