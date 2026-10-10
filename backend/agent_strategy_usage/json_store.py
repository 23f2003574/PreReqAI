from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentStrategyUsage
from .store import LLMAgentStrategyUsageStore


class JsonLLMAgentStrategyUsageStore(LLMAgentStrategyUsageStore):
    """Persists durable LLM agent strategy usage records to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, usage: LLMAgentStrategyUsage) -> LLMAgentStrategyUsage:
        usages = self.file.read()
        usages[usage.usage_id] = usage.to_dict()
        self.file.write(usages)
        return usage

    def get(self, usage_id: str):
        usages = self.file.read()
        data = usages.get(usage_id)
        return None if data is None else LLMAgentStrategyUsage.from_dict(data)

    def list_for_strategy(self, strategy_id: str):
        usages = self.file.read()
        matching = [
            LLMAgentStrategyUsage.from_dict(data)
            for data in usages.values()
            if data.get("strategy_id") == strategy_id
        ]
        return sorted(matching, key=lambda item: item.created_at)

    def list_for_execution(self, execution_id: str):
        usages = self.file.read()
        matching = [
            LLMAgentStrategyUsage.from_dict(data)
            for data in usages.values()
            if data.get("execution_id") == execution_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
