from copy import deepcopy

from .models import LLMAgentStrategyUsage
from .store import LLMAgentStrategyUsageStore


class InMemoryLLMAgentStrategyUsageStore(LLMAgentStrategyUsageStore):
    """Stores durable LLM agent strategy usage records in memory, for
    development and testing."""

    def __init__(self):
        self._usages: dict[str, LLMAgentStrategyUsage] = {}

    def save(self, usage: LLMAgentStrategyUsage) -> LLMAgentStrategyUsage:
        stored = deepcopy(usage)
        self._usages[usage.usage_id] = stored
        return deepcopy(stored)

    def get(self, usage_id: str):
        usage = self._usages.get(usage_id)
        return deepcopy(usage) if usage is not None else None

    def list_for_strategy(self, strategy_id: str):
        matching = [usage for usage in self._usages.values() if usage.strategy_id == strategy_id]
        return [deepcopy(usage) for usage in sorted(matching, key=lambda item: item.created_at)]

    def list_for_execution(self, execution_id: str):
        matching = [usage for usage in self._usages.values() if usage.execution_id == execution_id]
        return [deepcopy(usage) for usage in sorted(matching, key=lambda item: item.created_at)]
