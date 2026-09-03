from copy import deepcopy
from datetime import datetime, timezone

from .models import LLMAgentStrategy
from .store import LLMAgentStrategyStore


class InMemoryLLMAgentStrategyStore(LLMAgentStrategyStore):
    """Stores durable LLM agent strategies in memory, for development and testing."""

    def __init__(self):
        self._strategies: dict[str, LLMAgentStrategy] = {}

    def save(self, strategy: LLMAgentStrategy) -> LLMAgentStrategy:
        strategy.updated_at = datetime.now(timezone.utc)
        stored = deepcopy(strategy)
        self._strategies[strategy.strategy_id] = stored
        return deepcopy(stored)

    def get(self, strategy_id: str):
        strategy = self._strategies.get(strategy_id)
        return deepcopy(strategy) if strategy is not None else None

    def list_for_scope(self, scope_id: str, status: str = None):
        matching = [
            strategy
            for strategy in self._strategies.values()
            if strategy.scope_id == scope_id
            and (status is None or strategy.status == status)
        ]
        return [
            deepcopy(strategy)
            for strategy in sorted(matching, key=lambda item: item.created_at)
        ]
