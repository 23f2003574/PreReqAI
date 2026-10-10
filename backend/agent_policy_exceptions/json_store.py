from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentPolicyException
from .store import LLMAgentPolicyExceptionStore


class JsonLLMAgentPolicyExceptionStore(LLMAgentPolicyExceptionStore):
    """Persists durable LLM agent policy exceptions to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, exception: LLMAgentPolicyException) -> LLMAgentPolicyException:
        exceptions = self.file.read()
        exceptions[exception.exception_id] = exception.to_dict()
        self.file.write(exceptions)
        return exception

    def get(self, exception_id: str):
        exceptions = self.file.read()
        data = exceptions.get(exception_id)
        return None if data is None else LLMAgentPolicyException.from_dict(data)

    def list_for_scope(self, scope_id: str, status: str = None):
        exceptions = self.file.read()
        matching = [
            LLMAgentPolicyException.from_dict(data)
            for data in exceptions.values()
            if data.get("scope_id") == scope_id and (status is None or data.get("status") == status)
        ]
        return sorted(matching, key=lambda item: item.created_at)
