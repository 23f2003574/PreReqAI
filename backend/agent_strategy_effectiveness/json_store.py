from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentStrategyOutcome
from .store import LLMAgentStrategyOutcomeStore


class JsonLLMAgentStrategyOutcomeStore(LLMAgentStrategyOutcomeStore):
    """Persists durable LLM agent strategy outcomes to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, outcome: LLMAgentStrategyOutcome) -> LLMAgentStrategyOutcome:
        outcomes = self.file.read()
        outcomes[outcome.outcome_id] = outcome.to_dict()
        self.file.write(outcomes)
        return outcome

    def get(self, outcome_id: str):
        outcomes = self.file.read()
        data = outcomes.get(outcome_id)
        return None if data is None else LLMAgentStrategyOutcome.from_dict(data)

    def list_for_strategy(self, strategy_id: str):
        outcomes = self.file.read()
        matching = [
            LLMAgentStrategyOutcome.from_dict(data)
            for data in outcomes.values()
            if data.get("strategy_id") == strategy_id
        ]
        return sorted(matching, key=lambda item: item.created_at)
