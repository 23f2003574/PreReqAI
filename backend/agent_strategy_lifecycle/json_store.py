from pathlib import Path

from backend.storage import AtomicJsonFile

from .models import LLMAgentStrategyLifecycleDecision
from .store import LLMAgentStrategyLifecycleStore


class JsonLLMAgentStrategyLifecycleStore(LLMAgentStrategyLifecycleStore):
    """Persists durable LLM agent strategy lifecycle decisions to a JSON file."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, decision: LLMAgentStrategyLifecycleDecision) -> LLMAgentStrategyLifecycleDecision:
        decisions = self.file.read()
        decisions[decision.decision_id] = decision.to_dict()
        self.file.write(decisions)
        return decision

    def get(self, decision_id: str):
        decisions = self.file.read()
        data = decisions.get(decision_id)
        return None if data is None else LLMAgentStrategyLifecycleDecision.from_dict(data)

    def list_for_strategy(self, strategy_id: str):
        decisions = self.file.read()
        matching = [
            LLMAgentStrategyLifecycleDecision.from_dict(data)
            for data in decisions.values()
            if data.get("strategy_id") == strategy_id
        ]
        return sorted(matching, key=lambda item: item.decided_at)
