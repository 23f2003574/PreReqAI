from copy import deepcopy

from .models import LLMAgentStrategyLifecycleDecision
from .store import LLMAgentStrategyLifecycleStore


class InMemoryLLMAgentStrategyLifecycleStore(LLMAgentStrategyLifecycleStore):
    """Stores durable LLM agent strategy lifecycle decisions in memory,
    for development and testing."""

    def __init__(self):
        self._decisions: dict[str, LLMAgentStrategyLifecycleDecision] = {}

    def save(self, decision: LLMAgentStrategyLifecycleDecision) -> LLMAgentStrategyLifecycleDecision:
        stored = deepcopy(decision)
        self._decisions[decision.decision_id] = stored
        return deepcopy(stored)

    def get(self, decision_id: str):
        decision = self._decisions.get(decision_id)
        return deepcopy(decision) if decision is not None else None

    def list_for_strategy(self, strategy_id: str):
        matching = [
            decision for decision in self._decisions.values() if decision.strategy_id == strategy_id
        ]
        return [deepcopy(decision) for decision in sorted(matching, key=lambda item: item.decided_at)]
