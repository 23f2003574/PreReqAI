from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMProjectContext
from .store import LLMProjectContextStore


class JsonLLMProjectContextStore(LLMProjectContextStore):
    """Persists durable LLM project context to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, context: LLMProjectContext) -> LLMProjectContext:
        context.updated_at = datetime.now(timezone.utc)

        contexts = self.file.read()
        contexts[context.context_id] = context.to_dict()
        self.file.write(contexts)

        return deepcopy(context)

    def get(self, context_id: str):
        contexts = self.file.read()
        data = contexts.get(context_id)
        return None if data is None else LLMProjectContext.from_dict(data)

    def delete(self, context_id: str) -> bool:
        contexts = self.file.read()
        if context_id not in contexts:
            return False
        del contexts[context_id]
        self.file.write(contexts)
        return True

    def list_for_scope(self, scope_id: str, context_type=None):
        contexts = self.file.read()
        matching = [
            LLMProjectContext.from_dict(data)
            for data in contexts.values()
            if data.get("scope_id") == scope_id
            and (context_type is None or data.get("context_type") == context_type)
        ]
        return sorted(matching, key=lambda item: item.created_at)
