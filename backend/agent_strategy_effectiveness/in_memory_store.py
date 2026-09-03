from copy import deepcopy

from .models import LLMAgentStrategyOutcome
from .store import LLMAgentStrategyOutcomeStore


class InMemoryLLMAgentStrategyOutcomeStore(LLMAgentStrategyOutcomeStore):
    """Stores durable LLM agent strategy outcomes in memory, for
    development and testing."""

    def __init__(self):
        self._outcomes: dict[str, LLMAgentStrategyOutcome] = {}

    def save(self, outcome: LLMAgentStrategyOutcome) -> LLMAgentStrategyOutcome:
        stored = deepcopy(outcome)
        self._outcomes[outcome.outcome_id] = stored
        return deepcopy(stored)

    def get(self, outcome_id: str):
        outcome = self._outcomes.get(outcome_id)
        return deepcopy(outcome) if outcome is not None else None

    def list_for_strategy(self, strategy_id: str):
        matching = [
            outcome for outcome in self._outcomes.values() if outcome.strategy_id == strategy_id
        ]
        return [deepcopy(outcome) for outcome in sorted(matching, key=lambda item: item.created_at)]
