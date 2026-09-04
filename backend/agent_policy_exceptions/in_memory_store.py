from copy import deepcopy

from .models import LLMAgentPolicyException
from .store import LLMAgentPolicyExceptionStore


class InMemoryLLMAgentPolicyExceptionStore(LLMAgentPolicyExceptionStore):
    """Stores durable LLM agent policy exceptions in memory, for development and testing."""

    def __init__(self):
        self._exceptions: dict[str, LLMAgentPolicyException] = {}

    def save(self, exception: LLMAgentPolicyException) -> LLMAgentPolicyException:
        stored = deepcopy(exception)
        self._exceptions[exception.exception_id] = stored
        return deepcopy(stored)

    def get(self, exception_id: str):
        exception = self._exceptions.get(exception_id)
        return deepcopy(exception) if exception is not None else None

    def list_for_scope(self, scope_id: str, status: str = None):
        matching = [
            exception
            for exception in self._exceptions.values()
            if exception.scope_id == scope_id and (status is None or exception.status == status)
        ]
        return [deepcopy(exception) for exception in sorted(matching, key=lambda item: item.created_at)]
