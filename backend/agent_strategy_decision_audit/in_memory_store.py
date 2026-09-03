from copy import deepcopy

from .models import LLMAgentStrategyDecision
from .store import LLMAgentStrategyDecisionStore


class InMemoryLLMAgentStrategyDecisionStore(LLMAgentStrategyDecisionStore):
    """Stores durable LLM agent strategy decision audit records in memory,
    for development and testing."""

    def __init__(self):
        self._decisions: dict[str, LLMAgentStrategyDecision] = {}

    def save(self, decision: LLMAgentStrategyDecision) -> LLMAgentStrategyDecision:
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
        return [deepcopy(decision) for decision in sorted(matching, key=lambda item: item.created_at)]

    def list_for_execution(self, execution_or_task_id: str):
        matching = [
            decision for decision in self._decisions.values()
            if decision.execution_or_task_id == execution_or_task_id
        ]
        return [deepcopy(decision) for decision in sorted(matching, key=lambda item: item.created_at)]
