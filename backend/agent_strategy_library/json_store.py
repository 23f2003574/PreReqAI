from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentStrategy
from .store import LLMAgentStrategyStore


class JsonLLMAgentStrategyStore(LLMAgentStrategyStore):
    """Persists durable LLM agent strategies to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, strategy: LLMAgentStrategy) -> LLMAgentStrategy:
        strategy.updated_at = datetime.now(timezone.utc)

        strategies = self.file.read()
        strategies[strategy.strategy_id] = strategy.to_dict()
        self.file.write(strategies)

        return deepcopy(strategy)

    def get(self, strategy_id: str):
        strategies = self.file.read()
        data = strategies.get(strategy_id)
        return None if data is None else LLMAgentStrategy.from_dict(data)

    def list_for_scope(self, scope_id: str, status: str = None):
        strategies = self.file.read()
        matching = [
            LLMAgentStrategy.from_dict(data)
            for data in strategies.values()
            if data.get("scope_id") == scope_id
            and (status is None or data.get("status") == status)
        ]
        return sorted(matching, key=lambda item: item.created_at)
